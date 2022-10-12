#!/usr/bin/env python
"""
Get session list with metadata from remote database and write to CSV

AUTHOR : Mike Tyszka
PLACE  : Caltech
DATES  : 2022-10-11 JMT From scratch
"""

import argparse
import pandas as pd

from pydicom import Dataset

from pynetdicom import (AE, evt, debug_logger, _config, StoragePresentationContexts)
import pynetdicom.sop_class as psc


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Retrieve session list from remote DICOM server')

    parser.add_argument('-ip', '--ipaddress',
                        default='127.0.0.1',
                        help='Remote DICOM server IP address')

    parser.add_argument('-p', '--port',
                        default=11112,
                        type=int,
                        help='Remote DICOM server port')

    args = parser.parse_args()

    # Horos IP and port
    addr = args.ipaddress
    port = args.port

    print('DICOMKIT List Remote Sessions')
    print('-----------------------------')
    print(f'Remote Host IP : {addr}:{port}')

    # Query all remote sessions
    study_df = find_sessions(addr, port)

    # Save study dataframe to CSV file
    csv_fname = 'StudyList.csv'
    print(f'\nSaving study list to {csv_fname}')
    study_df.to_csv(csv_fname, index=False)


def find_sessions(addr, port):

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    # Horos uses a StudyRoot model for Q&R
    ae.add_requested_context(psc.StudyRootQueryRetrieveInformationModelFind)

    # Associate with peer AE
    assoc = ae.associate(addr, port)

    # Create a study level query
    ds = Dataset()
    ds.QueryRetrieveLevel = 'STUDY'
    ds.PatientID = '*'

    # Metadata to retrieve
    ds.StudyDate = ''
    ds.StudyTime = ''
    ds.ReferringPhysicianName = ''
    ds.AccessionNumber = ''

    # Capture study and series UIDs for C-MOVE
    uids = []

    if assoc.is_established:

        print('Association with {}:{} established'.format(addr, port))
        print('')

        # Use the C-FIND service to send the identifier
        responses = assoc.send_c_find(ds, psc.StudyRootQueryRetrieveInformationModelFind)

        for (status, identifier) in responses:

            if status:

                if status.Status & 0xF000 == 0xC000:
                    print("* Could not process query")

                # If the status is 'Pending' then identifier is the C-FIND response
                if status.Status == 0xFF00:

                    print('Querying {}'.format(identifier.PatientID))

                    # Add study and series UIDs to collection
                    uids.append((
                        identifier.PatientID,
                        identifier.StudyDate,
                        identifier.StudyTime,
                        identifier.ReferringPhysicianName,
                        identifier.AccessionNumber
                    ))

            else:

                print('Connection timed out, was aborted or received invalid response')

        # Convert list to dataframe
        study_df = pd.DataFrame(uids, columns=[
            'PatientID', 'Date', 'Time', 'RefPhys', 'AccessNum'
        ])

        # Release the association
        print('\nRequesting remote association release')
        assoc.release()
        print('Remote association closed')

    else:

        print('Association rejected, aborted or never connected')
        study_df = pd.DataFrame()

    return study_df


if "__main__" in __name__:

    main()