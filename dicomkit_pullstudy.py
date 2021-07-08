#!/usr/bin/env python

import argparse

from pynetdicom import AE
from pydicom.dataset import Dataset
from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelFind

def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Retrieve studies from a DICOM server')

    parser.add_argument('-s', '--subjectname', help='Subject Name')

    args = parser.parse_args()

    addr = '131.215.9.86'
    port = 11112

    # Test C-ECHO response from server
    test_cecho(addr, port)

    # Test simple query of remote server
    patient_search = "QC*"
    patient_list = test_query(addr, port, patient_search)

    # Get the first study from the remote server
    get_patient(addr, port, patient_list[0])


def test_cecho(addr, port):

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


def test_query(addr, port, patient_search):

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    # Horos uses a StudyRoot model for Q&R
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)

    # Associate with peer AE
    assoc = ae.associate(addr, port)

    # Create our Identifier (query) dataset
    ds = Dataset()
    ds.PatientName = patient_search
    ds.QueryRetrieveLevel = 'STUDY'

    patient_list = []

    if assoc.is_established:

        # Use the C-FIND service to send the identifier
        responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)

        for (status, identifier) in responses:

            if status:

                # print('C-FIND query status: 0x{0:04x}'.format(status.Status))

                if status.Status & 0xF000 == 0xC000:
                    print("* Could not process query")

                # If the status is 'Pending' then identifier is the C-FIND response
                if status.Status in (0xFF00, 0xFF01):

                    print('Found patient {}'.format(identifier.PatientName))

                    patient_list.append(identifier.PatientName)

            else:

                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()

    else:

        print('Association rejected, aborted or never connected')

    return patient_list

def get_patient(addr, port, patname):

    pass


if "__main__" in __name__:

    main()