#!/usr/bin/env python
"""
Pull all physio DICOM files (*_Physiolog) from a Horos server

AUTHOR : Mike Tyszka
PLACE  : Caltech
DATES  : 2021-07-13 JMT From scratch
         2021-07-15 JMT Add subject list text file argument
"""

import os
import sys
import argparse
import pandas as pd
from pydicom import Dataset
from pynetdicom import (AE, evt, debug_logger, _config)
import pynetdicom.sop_class as psc


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Retrieve studies from a DICOM server')

    parser.add_argument('-s', '--subjectlist', default='',
                        help='Subject ID text file, one ID per line ['' -> All subjects]')
    parser.add_argument('-od', '--outputdir', default='dicom',
                        help="Destination directory ['./dicom']")
    parser.add_argument('-ra', '--remoteaddr', required=True,
                        help='IP address or hostname of remote SCP')
    parser.add_argument('-rp', '--remoteport', type=int, required=True,
                        help='Port of remote SCP')
    parser.add_argument('-lae', '--localaet', default='LOCAL_STORE_SCP',
                        help="Local store SCP AE title ['LOCAL_STORE_SCP']")
    parser.add_argument('-lp', '--localport', type=int, default='11114',
                        help="Local store SCP port ['11114']")

    args = parser.parse_args()
    subj_list_fname = args.subjectlist

    remote_addr = args.remoteaddr
    remote_port = int(args.remoteport)
    local_aet = args.localaet
    local_port = int(args.localport)

    # Search for CMRR MB EPI Physio log DICOMs
    series_search = "*Physiolog"

    # Load subject list from file
    if subj_list_fname:
        try:
            print('Loading subject list from {}'.format(subj_list_fname))
            subj_df = pd.read_csv(subj_list_fname, sep=',', header=None)
            subject_list = subj_df[0].values
        except FileNotFoundError as err:
            print('* Subject list {} not found - exiting'.format(subj_list_fname))
            sys.exit(1)

    # Query remote SCP using a series description search expression
    # Returns list of Patient ID, Series Description, Study UID, Series UID for matches
    uids = find_series(remote_addr, remote_port, series_search)

    # C-MOVE all Physiolog series from the Horos server to a local directory
    # Exclude Subject/Patient IDs not in subject_list
    retrieve_series(remote_addr, remote_port, local_aet, local_port, uids, subject_list)


def find_series(remote_addr, remote_port, series_search):
    """
    Perform series level query of remote SCP

    :param remote_addr: str
        IP address or hostname of remote SCP
    :param remote_port: int
        Port number of remote SCP
    :param series_search: str
        Series-level search term (wildcards allowed)
    :return:
    """

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    # Horos uses a StudyRoot model for Q&R
    ae.add_requested_context(psc.StudyRootQueryRetrieveInformationModelFind)

    # Associate with peer AE
    assoc = ae.associate(remote_addr, remote_port)

    # Create a study level query
    ds = Dataset()
    ds.QueryRetrieveLevel = 'SERIES'
    ds.PatientID = ''
    ds.SeriesDescription = series_search
    ds.StudyInstanceUID = ''
    ds.SeriesInstanceUID = ''

    # Capture study and series UIDs for C-MOVE
    uids = []

    if assoc.is_established:

        print('Association with {}:{} established'.format(remote_addr, remote_port))

        # Use the C-FIND service to send the identifier
        responses = assoc.send_c_find(ds, psc.StudyRootQueryRetrieveInformationModelFind)

        for (status, identifier) in responses:

            if status:

                if status.Status & 0xF000 == 0xC000:
                    print("* Could not process query")

                # If the status is 'Pending' then identifier is the C-FIND response
                if status.Status == 0xFF00:

                    print('')
                    print('Pending {} : {}'.format(identifier.PatientID, identifier.SeriesDescription))
                    print('  Study Instance UID  : {}'.format(identifier.StudyInstanceUID))
                    print('  Series Instance UID : {}'.format(identifier.SeriesInstanceUID))

                    # At study and series UIDs to collection
                    uids.append((identifier.PatientID,
                                 identifier.SeriesDescription,
                                 identifier.StudyInstanceUID,
                                 identifier.SeriesInstanceUID))

            else:

                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        print('')
        print('Releasing remote association')
        assoc.release()
        print('Done')

    else:

        print('Association rejected, aborted or never connected')

    return uids


def retrieve_series(remote_addr, remote_port, local_aet, local_port, uids, subject_list, debug=False):
    """
    Retrieve study/series specified in UID info list from remote SCP

    :param remote_addr: str
        Remote SCP IP address or hostname
    :param remote_port: int
        Remote SCP port
    :param local_ae: str
        Local STORE SCP AE title
    :param local_port: int
        Local STORE SCP port
    :param uids: list
        List of tuples containing patient/study/series UID info
    :param subject_list: list of str
        Allowed subject/patient IDs (exclude IDs not in this list)
    :param debug: bool
        Debug flag
    :return:
    """

    print('')
    print('-----------------')
    print('RETRIEVING SERIES')
    print('-----------------')
    print('')

    # Always accept storage requests and treat unknown presentation contexts as
    # part of the storage service.
    _config.UNRESTRICTED_STORAGE_SERVICE = True

    if debug:
        debug_logger()

    # Create our local Application Entity
    ae = AE()

    # Add presentation context (QR Move)
    ae.add_requested_context(psc.StudyRootQueryRetrieveInformationModelMove)

    # 2021-07-14 JMT No longer required with UNRESTRICTED_STORAGE_SERVICE = True
    # # Add all standard storage presentation contexts
    # ae.supported_contexts = AllStoragePresentationContexts
    #
    # # Add support for Siemens private SOP context
    # ae.add_supported_context('1.3.12.2.1107.5.9.1')

    # Setup local STORE event handler to write DICOM file to disk
    handlers = [(evt.EVT_C_STORE, handle_store)]

    # Start our local store SCP to catch incoming data
    print('Starting local storage SCP {} on remote_port {}'.format(local_aet, local_port))
    local_scp = ae.start_server(('', local_port), block=False, evt_handlers=handlers)

    # Loop over all patient/study/series UID info
    for uid in uids:

        # Unpack UID info
        pat_id, ser_desc, study_uid, series_uid = uid

        if pat_id in subject_list:

            # Create a new series level query dataset
            ds = Dataset()
            ds.QueryRetrieveLevel = 'SERIES'
            ds.PatientID = pat_id
            ds.StudyInstanceUID = study_uid
            ds.SeriesInstanceUID = series_uid
            ds.SeriesDate = []

            # Associate our local AE with the remote AE for C-MOVE and C-STORE
            assoc = ae.associate(remote_addr, remote_port)

            if assoc.is_established:

                print('')
                print('Remote association with {}:{} established'.format(remote_addr, remote_port))
                print('Sending C-MOVE for {} : {}'.format(pat_id, ser_desc))

                # Send a C-MOVE request to the remote AE
                responses = assoc.send_c_move(ds, local_aet, psc.StudyRootQueryRetrieveInformationModelMove)

                # Iterate over responses
                for (status, identifier) in responses:

                    if status:

                        s = status.Status
                        msg = ''

                        if s == 0x0000:
                            msg = 'Success!'
                        elif s in [0xFF00, 0xFF01]:
                            msg = 'Pending ...'
                        elif s & 0xF000 == 0xC000:
                            msg = 'Unable to process'
                        elif s == 0xa702:
                            msg = 'Out of Resources - Unable to perform sub-operation'
                        elif s == 0xa801:
                            msg = 'Refused: Move destination unknown'
                        else:
                            msg = 'Unknown response'

                        print('  Response 0x{:04x} : {:s}'.format(s, msg))

                    else:

                        print('Connection timed out, was aborted or received invalid response')

                print('  Releasing remote association')
                assoc.release()

            else:

                print('Association rejected, aborted or never connected')

    # Shut down local store SCP
    local_scp.shutdown()


def handle_store(event):
    """
    Handle a C-STORE request event
    """

    # Decode the C-STORE request's *Data Set* parameter to a pydicom Dataset
    ds = event.dataset

    # Add the File Meta Information
    ds.file_meta = event.file_meta

    # Create output directory if needed
    out_dir = 'dicom'
    os.makedirs(out_dir, exist_ok=True)

    # Save the dataset using the SOP Instance UID as the filename
    out_fname = 'sub-{}_ses-{}_{}.dcm'.format(ds.PatientID, ds.SeriesDate, ds.SeriesDescription)
    out_path = os.path.join(out_dir, out_fname)
    ds.save_as(out_path, write_like_original=False)

    # Return a 'Success' status
    return 0x0000


if "__main__" in __name__:

    main()