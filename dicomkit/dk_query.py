#!/usr/bin/env python
"""
Get session list with metadata from remote database and write to CSV

AUTHOR : Mike Tyszka
PLACE  : Caltech
DATES  : 2022-10-11 JMT From scratch
"""

import argparse
from .utils import find_studies


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
    study_df = find_studies(addr, port)

    # Save study_row dataframe to CSV file
    csv_fname = 'StudyList.csv'
    print(f'\nSaving study list to {csv_fname}')
    study_df.to_csv(csv_fname, index=False)


if "__main__" in __name__:

    main()