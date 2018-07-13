#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Jérôme Eberhardt 2016-2018
# Unrolr
#
# Function to read and save data from/to a HDF5 file
# Author: Jérôme Eberhardt <qksonoe@gmail.com>
#
# License: MIT


import h5py
import numpy as np

__author__ = "Jérôme Eberhardt"
__copyright__ = "Copyright 2018, Jérôme Eberhardt"

__lience__ = "MIT"
__maintainer__ = "Jérôme Eberhardt"
__email__ = "qksoneo@gmail.com"


def read_dataset(fname, dname, start=0, stop=-1, skip=1):

    data = None

    try:
        with h5py.File(fname, 'r') as f:
            if stop == -1:
                return f[dname][start::skip,]
            else:
                return f[dname][start:stop:skip,]
    except IOError:
        print("Error: cannot find file %s" % fname)

    return data

def save_dataset(fname, dname, data):
    with h5py.File(fname, 'w') as w:
        try:
            dset = w.create_dataset(dname, (data.shape[0], data.shape[1]))
            dset[:] = data
        except:
            pass

        w.flush()
