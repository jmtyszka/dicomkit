#!/usr/bin/env python
"""
Pull all physio DICOM files (*_Physiolog) from a Horos server

AUTHOR : Mike Tyszka
PLACE  : Caltech
DATES  : 2021-07-13 JMT From scratch
"""

import os
import argparse

from pynetdicom import (AE, evt, AllStoragePresentationContexts, debug_logger)
from pydicom.dataset import Dataset


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

    # Hard code QR model
    # Declared in sop_class in pynetdicom 2.0
    StudyRootQueryRetrieveInformationModelFind= '1.2.840.10008.5.1.4.1.2.2.1'

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    # Horos uses a StudyRoot model for Q&R
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)

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
        responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)

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

    print('')
    print('-----------------')
    print('RETRIEVING SERIES')
    print('-----------------')
    print('')

    if debug:
        debug_logger()

    # Create our local Application Entity
    ae = AE()

    # Add presentation context (QR Move)
    StudyRootQueryRetrieveInformationModelMove= '1.2.840.10008.5.1.4.1.2.2.2'
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)

    # Unfussy storage presentation contexts
    ae.supported_contexts = AllStoragePresentationContexts

    # Start our local store SCP to catch incoming data
    local_aet = 'LOCAL_STORE_SCP'
    local_port = 11113
    handlers = [(evt.EVT_C_STORE, handle_store)]

    print('Starting local storage SCP {} on port {}'.format(local_aet, local_port))
    local_scp = ae.start_server(('', local_port), block=False, evt_handlers=handlers)

    # Associate our local AE with the remote AE for C-MOVE and C-STORE
    assoc = ae.associate(remote_addr, remote_port)

    if assoc.is_established:

        print('Remote association with {}:{} established'.format(remote_addr, remote_port))

        # Loop over all series found by C-FIND above
        for uid in uids:

            # Unpack UID info
            pat_id, ser_desc, study_uid, series_uid = uid

            # Create a series level query dataset
            ds = Dataset()
            ds.QueryRetrieveLevel = 'SERIES'
            ds.PatientID = pat_id
            ds.StudyInstanceUID = study_uid
            ds.SeriesInstanceUID = series_uid

            print('Sending C-MOVE for {} : {}'.format(pat_id, ser_desc))

            # Send a C-MOVE request to the remote AE
            responses = assoc.send_c_move(ds, local_aet, StudyRootQueryRetrieveInformationModelMove)

            for (status, identifier) in responses:

                if status:

                    if status.Status == 0xFF00:
                        print('  Pending')

                    if status.Status & 0xF000 == 0xC000:
                        print("* Unable to process")

                    if status.Status == 0xa702:
                        print('* Refused: Out of Resources - Unable to perform sub-operation')

                else:

                    print('Connection timed out, was aborted or received invalid response')

        # Release the association
        print('')
        print('Releasing remote association')
        assoc.release()
        print('Done')

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

    # Create output directory
    out_dir = ds.PatientID
    os.makedirs(out_dir, exist_ok=True)

    # Save the dataset using the SOP Instance UID as the filename
    out_fname = '{}-{}.dcm'.format(ds.PatientID, ds.SeriesDescription)
    out_path = os.path.join(out_dir, out_fname)
    ds.save_as(out_path, write_like_original=False)

    # Return a 'Success' status
    return 0x0000


if "__main__" in __name__:

    main()