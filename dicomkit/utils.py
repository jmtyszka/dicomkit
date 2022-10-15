"""
DICOM query and retrieve utility functions

AUTHOR : Mike Tyszka
PLACE  : Caltech
DATES  : 2022-10-14 JMT From scratch
"""

import os
import sys
import subprocess
import shutil
import os.path as op
import pandas as pd
from pydicom import Dataset
from pynetdicom import (AE, evt, debug_logger, _config, StoragePresentationContexts)
import pynetdicom.sop_class as psc


def find_studies(addr, port, pat_id='*', ref_phys='*'):

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    # Horos uses a StudyRoot model for Q&R
    ae.add_requested_context(psc.StudyRootQueryRetrieveInformationModelFind)

    # Associate with peer AE
    assoc = ae.associate(addr, port)

    # Create a study_row level query
    ds = Dataset()
    ds.QueryRetrieveLevel = 'STUDY'
    ds.PatientID = f"{pat_id}*"
    ds.ReferringPhysicianName = ref_phys

    # Metadata to retrieve
    ds.StudyDate = ''
    ds.StudyTime = ''
    ds.StudyDescription = ''
    ds.StudyInstanceUID = ''
    ds.AdmittingDiagnosesDescription = ''
    ds.AccessionNumber = ''

    # Capture study_row and series UIDs for C-MOVE
    uids = []

    if assoc.is_established:

        print(f'\nRemote Association with {addr}:{port} established')
        print(f'Searching for:')
        print(f'  Patient ID : {pat_id}')
        print(f'  Ref Phys   : {ref_phys}')

        # Use the C-FIND service to send the identifier
        responses = assoc.send_c_find(ds, psc.StudyRootQueryRetrieveInformationModelFind)

        for (status, identifier) in responses:

            if status:

                if status.Status & 0xF000 == 0xC000:
                    print("* Could not process query")

                # If the status is 'Pending' then identifier is the C-FIND response
                if status.Status == 0xFF00:

                    print('Found {}'.format(identifier.PatientID))

                    # Add study_row and series UIDs to collection
                    uids.append((
                        identifier.PatientID,
                        identifier.StudyDate,
                        identifier.StudyTime,
                        identifier.ReferringPhysicianName,
                        identifier.AccessionNumber,
                        identifier.StudyInstanceUID
                    ))

            else:

                print('Connection timed out, was aborted or received invalid response')

        # Convert list to dataframe
        print(f'\nFound {len(uids)} studies')
        print('Building data frame')
        study_df = pd.DataFrame(uids, columns=[
            'PatientID', 'Date', 'Time', 'RefPhys', 'AccessNum', 'StudyInstanceUID'
        ])

        # Release the association
        print('\nRequesting remote association release')
        assoc.release()
        print('Remote association closed')

    else:

        print('Association rejected, aborted or never connected')
        study_df = pd.DataFrame()

    return study_df


def retrieve_studies(remote_addr, remote_port, study_row, out_dir='dicom', debug=False):
    """
    Retrieve studies specified in study dataframe

    :param remote_addr: str
        Remote SCP IP address or hostname
    :param remote_port: int
        Remote SCP port
    :param study_row: Series
        Study metadata
    :param out_dir: pathlike
        Output directory for retrieved DICOM files
    :param debug: bool
        Debug flag
    :return:
    """

    print('')
    print('------------------')
    print('RETRIEVING STUDIES')
    print('------------------')
    print('')

    # Always accept storage requests and treat unknown presentation contexts as
    # part of the storage service.
    _config.UNRESTRICTED_STORAGE_SERVICE = True

    if debug:
        debug_logger()

    # Create our local Application Entity
    local_aet = 'dicomkit'
    local_port = 11113
    ae = AE(ae_title=local_aet)

    # Add presentation context (QR Move)
    ae.add_requested_context(psc.StudyRootQueryRetrieveInformationModelMove)

    # Start our local store SCP to catch incoming data
    handlers = [(evt.EVT_C_STORE, handle_store)]

    print('Starting local storage SCP {} on port {}'.format(local_aet, local_port))
    local_scp = ae.start_server(('', local_port), block=False, evt_handlers=handlers)

    # Create a new series level query dataset
    ds = Dataset()
    ds.QueryRetrieveLevel = 'STUDY'
    ds.PatientID = study_row['PatientID']
    ds.StudyInstanceUID = study_row['StudyInstanceUID']

    # Associate our local AE with the remote AE for C-MOVE and C-STORE
    assoc = ae.associate(remote_addr, remote_port)

    if assoc.is_established:

        print(f'\nRemote association with {remote_addr}:{remote_port} established')
        print(f"Sending C-MOVE for {study_row['PatientID']}")

        # Send a C-MOVE request to the remote AE
        responses = assoc.send_c_move(ds, local_aet, psc.StudyRootQueryRetrieveInformationModelMove)

        # Message visibility toggle
        show_msg = True

        # Iterate over responses
        for (status, identifier) in responses:

            if status:

                s = status.Status
                msg = ''

                if s == 0x0000:
                    msg = 'SUCCESS!'
                elif s in [0xFF00, 0xFF01]:
                    if show_msg:
                        print('Waiting for move to complete ...')
                    show_msg = False
                elif s & 0xF000 == 0xC000:
                    msg = 'FAILURE: Unable to process'
                elif s == 0xa702:
                    msg = 'FAILURE: Unable to perform sub-operation'
                elif s == 0xa801:
                    msg = 'FAILURE: Move destination unknown'

                if msg and show_msg:
                    print('  Response 0x{:04x} : {:s}'.format(s, msg))

            else:

                print('Connection timed out, was aborted or received invalid response')

        print('Releasing remote association')
        assoc.release()

    else:

        print('Association rejected, aborted or never connected')

    # Shut down local store SCP
    local_scp.shutdown()


def handle_store(event):
    """
    Handle a C-STORE request event
    """

    # Safe create output/ subdirectory of current working directory
    out_dir = op.realpath('dicom')
    os.makedirs(out_dir, exist_ok=True)

    # Decode the C-STORE request's *Data Set* parameter to a pydicom Dataset
    ds = event.dataset

    # Add the File Meta Information
    ds.file_meta = event.file_meta

    # Save the dataset using the SOP Instance UID as the filename
    out_path = op.join(out_dir, f'{ds.SOPInstanceUID}.dcm')
    ds.save_as(out_path, write_like_original=False)

    # Return a 'Success' status
    return 0x0000


def flywheel_ingest(cache_dir, fw_group_id, fw_project):

    # Build flywheel command
    fw_cmd = ['fw', 'ingest', 'dicom', '-y', cache_dir, fw_group_id, fw_project]

    print(f'Running : {fw_cmd}')

    # Run flywheel command
    p = subprocess.run(fw_cmd, stdout=sys.stdout, stderr=sys.stderr)

    # Clear cache folder
    clear_cache_dir(cache_dir)


def clear_cache_dir(cache_dir):

    # Delete and recreate cache directory
    if op.isdir(cache_dir):
        print('> Deleting cache folder')
        shutil.rmtree(cache_dir)
    print('> Creating cache folder')
    os.makedirs(cache_dir, exist_ok=True)
