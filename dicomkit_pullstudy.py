#!/usr/bin/env python

import argparse

from pynetdicom import AE, debug_logger
from pydicom.dataset import Dataset

def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Retrieve studies from a DICOM server')

    parser.add_argument('-s', '--subjectname', help='Subject Name')

    args = parser.parse_args()

    # Horos IP and port
    addr = '131.215.79.36'
    port = 11112

    # Test C-ECHO response from server
    ping_server(addr, port)

    # Test simple query of remote server
    patient_search = "Jmt*"
    series_search = "*Physiolog"

    results = find_patient_series(addr, port, patient_search, series_search)
    # results = move_patient_series(addr, port, patient_search, series_search)


def ping_server(addr, port):

    ae = AE(ae_title=b'MY_ECHO_SCU')

    # Verification SOP Class has a UID of 1.2.840.10008.1.1
    #   we can use the UID string directly when requesting the presentation
    #   contexts we want to use in the association
    ae.add_requested_context('1.2.840.10008.1.1')

    # Associate with a peer DICOM AE
    assoc = ae.associate(addr, port)

    if assoc.is_established:

        # Send a DIMSE C-ECHO request to the peer
        # `status` is a pydicom Dataset object with (at a minimum) a
        #   (0000,0900) Status element
        # If the peer hasn't accepted the requested context then this
        #   will raise a RuntimeError exception
        status = assoc.send_c_echo()

        # Output the response from the peer
        if status:
            print('C-ECHO Response: 0x{0:04x}'.format(status.Status))

        # Release the association
        assoc.release()


def find_patient_series(addr, port, patient_search, series_search):

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
    ds.PatientName = patient_search
    ds.SeriesDescription = series_search

    study_list = []

    if assoc.is_established:

        print('Association with {}:{} established'.format(addr, port))

        # Use the C-FIND service to send the identifier
        responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)

        for (status, identifier) in responses:

            if status:

                if status.Status & 0xF000 == 0xC000:
                    print("* Could not process query")

                # If the status is 'Pending' then identifier is the C-FIND response
                if status.Status in (0xFF00, 0xFF01):

                    print('Found {} {}'.format(identifier.PatientName, identifier.SeriesDescription))

            else:

                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        print('Releasing association')
        assoc.release()
        print('Done')
        print('')

    else:

        print('Association rejected, aborted or never connected')

    return study_list


def move_patient_series(addr, port, patient_search, series_search):

    debug_logger()

    # Hard code QR model
    # Declared in sop_class in pynetdicom 2.0
    StudyRootQueryRetrieveInformationModelMove= '1.2.840.10008.5.1.4.1.2.2.2'

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    # Horos uses a StudyRoot model for Q&R
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)

    # Create a series level query
    ds = Dataset()
    ds.QueryRetrieveLevel = 'STUDY'
    ds.PatientName = 'CC*'
    ds.SeriesDescription = '*Physiolog'

    # Associate with peer AE
    assoc = ae.associate(addr, port)

    study_list = []

    if assoc.is_established:

        print('Association with {}:{} established'.format(addr, port))

        # Use the C-MOVE service to send the identifier
        responses = assoc.send_c_move(ds, b'DICOMKIT_STORE', StudyRootQueryRetrieveInformationModelMove)

        for (status, identifier) in responses:

            print(status, identifier)

            if status:

                if status.Status & 0xF000 == 0xC000:
                    print("* Could not process query")

                if status.Status in (0xFF00, 0xFF01):
                    print('Found {} {}'.format(identifier.PatientName, identifier.SeriesDescription))

            else:

                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()

    else:

        print('Association rejected, aborted or never connected')

    return study_list


if "__main__" in __name__:

    main()