#!/usr/bin/env python
"""
Pull all physio DICOM files (*_Physiolog) from a Horos server

AUTHOR : Mike Tyszka
PLACE  : Caltech
DATES  : 2021-07-13 JMT From scratch
"""

import os
import argparse

from pydicom import Dataset

from pynetdicom import (AE, evt, debug_logger, _config)
import pynetdicom.sop_class as psc

def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Retrieve studies from a DICOM server')

    parser.add_argument('-s', '--subjectname', help='Subject Name')

    args = parser.parse_args()

    # Horos IP and port
    addr = '131.215.79.36'
    port = 11112

    # Search for CMRR MB EPI Physio log DICOMs
    # series_search = "*SBRef"
    series_search = "*Physiolog"

    uids = find_series(addr, port, series_search)

    # C-MOVE all Physiolog series from the Horos server to a local directory
    retrieve_series(addr, port, uids)


def find_series(addr, port, series_search):

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    # Horos uses a StudyRoot model for Q&R
    ae.add_requested_context(psc.StudyRootQueryRetrieveInformationModelFind)

    # Associate with peer AE
    assoc = ae.associate(addr, port)

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

        print('Association with {}:{} established'.format(addr, port))

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


def retrieve_series(remote_addr, remote_port, uids, debug=False):
    """
    Retrieve study/series specified in UID info list from remote SCP

    :param remote_addr: str
        Remote SCP IP address or hostname
    :param remote_port: int
        Remote SCP port
    :param uids: list
        List of tuples containing patient/study/series UID info
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

    # Start our local store SCP to catch incoming data
    local_aet = 'LOCAL_STORE_SCP'
    local_port = 11113
    handlers = [(evt.EVT_C_STORE, handle_store)]

    print('Starting local storage SCP {} on port {}'.format(local_aet, local_port))
    local_scp = ae.start_server(('', local_port), block=False, evt_handlers=handlers)

    # Loop over all patient/study/series UID info
    for uid in uids:

        # Unpack UID info
        pat_id, ser_desc, study_uid, series_uid = uid

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