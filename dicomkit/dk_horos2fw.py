#!/usr/bin/env python
"""
Transfer all patient studies in a Horos database to a Flywheel instance
using a provided CSV group-prefix to group-project mapping

AUTHOR : Mike Tyszka
PLACE  : Caltech
DATES  : 2021-10-14 JMT From scratch
"""

import os.path as op
import argparse
import pandas as pd
from .utils import (find_studies, retrieve_studies, flywheel_ingest, clear_cache_dir)


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Transfer patient studies from Horos to Flywheel')

    parser.add_argument('-m', '--mapcsv',
                        required=False,
                        default='*',
                        help='Horos to Flywheel CSV mapping table')

    parser.add_argument('-ip', '--ipaddress',
                        default='127.0.0.1',
                        help='Remote DICOM server IP address')

    parser.add_argument('-p', '--port',
                        default=11112,
                        type=int,
                        help='Remote DICOM server port')

    args = parser.parse_args()

    print('DICOMKIT Horos to Flywheel')
    print('--------------------------')
    print(f'Remote Host IP   : {args.ipaddress}:{args.port}')
    print(f'Mapping Table    : {args.mapcsv}')

    # Temporary DICOM cache folder
    cache_dir = op.realpath(op.join(op.curdir, 'dicom'))
    print(f'Cache folder     : {cache_dir}')

    # Clear cache
    clear_cache_dir(cache_dir)

    # Load mapping table
    map_df = pd.read_csv(args.mapcsv)

    # Loop over map rows
    for map_idx, map_row in map_df.iterrows():

        # Find all studies matching the current DICOM Group and Prefix
        study_df = find_studies(
            args.ipaddress, args.port,
            pat_id=map_row['DICOM Patient ID Prefix'],
            ref_phys=map_row['DICOM Group']
        )

        # Loop over all studies for this patient ID prefix and group
        for study_idx, study_row in study_df.iterrows():

            # Retrieve DICOM images for current study_row
            retrieve_studies(args.ipaddress, args.port, study_row, out_dir=cache_dir)

            # Upload DICOMs to Flywheel
            # Requires active login - run 'fw login <FW API key>' before this script
            flywheel_ingest(cache_dir, fw_group_id=map_row['FW Group'], fw_project=map_row['FW Project'])


if "__main__" in __name__:

    main()