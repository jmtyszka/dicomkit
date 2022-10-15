#!/usr/bin/env python
"""
Pull all physio DICOM files (*_Physiolog) from a Horos server for a given subject

AUTHOR : Mike Tyszka
PLACE  : Caltech
DATES  : 2021-07-13 JMT From scratch
"""


import argparse
from .utils import (find_studies, retrieve_studies)


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Retrieve studies from a DICOM server')

    parser.add_argument('-pid', '--patientid',
                        required=False,
                        default='*',
                        help='Patient ID')

    parser.add_argument('-ip', '--ipaddress',
                        default='127.0.0.1',
                        help='Remote DICOM server IP address')

    parser.add_argument('-p', '--port',
                        default=11112,
                        type=int,
                        help='Remote DICOM server port')

    parser.add_argument('-o', '--outdir',
                        default='dicom',
                        help='Output directory for retrieved DICOM files')

    args = parser.parse_args()

    print('DICOMKIT Patient Retriever')
    print('--------------------------')
    print(f'Remote Host IP   : {args.ipaddress}:{args.port}')
    print(f'Output directory : {args.outdir}')
    print(f'Patient ID       : {args.patientid}')

    study_df = find_studies(args.ipaddress, args.port, args.patientid)
    retrieve_studies(args.ipaddress, args.port, study_df, args.outdir)


if "__main__" in __name__:

    main()