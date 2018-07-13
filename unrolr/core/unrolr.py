#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Jérôme Eberhardt 2016-2018
# Unrolr
#
# The core of Unrolr (pSPE + dihedral distance as metric)
# Author: Jérôme Eberhardt <qksonoe@gmail.com>
#
# License: MIT


from __future__ import print_function

import os
import imp
import sys
import argparse

import h5py
import numpy as np
import pyopencl as cl

from ..utils import read_dataset

__author__ = "Jérôme Eberhardt"
__copyright__ = "Copyright 2018, Jérôme Eberhardt"

__lience__ = "MIT"
__maintainer__ = "Jérôme Eberhardt"
__email__ = "qksoneo@gmail.com"


class Unrolr():

    def __init__(self, r_neighbor, metric='dihedral', n_components=2, n_iter=10000,
                 random_seed=None, verbose=0):

        # Check PYOPENCL_CTX environnment variable
        if not self._check_environnment_variable("PYOPENCL_CTX"):
            print("Error: The environnment variable PYOPENCL_CTX is not defined !")
            print("Tip: python -c \"import pyopencl as cl; cl.create_some_context()\"")
            sys.exit(1)

        self.n_components = n_components
        self.r_neighbor = r_neighbor
        self.n_iter = n_iter
        self._metric = metric
        # Set numpy random state and verbose
        self.random_seed = self._set_random_state(random_seed)
        self.verbose = verbose

        self.learning_rate = 1.0
        self.epsilon = 1e-4

        self.embedding = None
        self.stress = None
        self.correlation = None

        # Read OpenCL kernel file
        path = imp.find_module('unrolr')[1]
        fname = path + '/core/kernel.cl'

        with open(fname) as f:
            self._kernel = f.read()

    def _check_environnment_variable(self, variable):
        """
        Check if an environnment variable exist or not
        """
        if os.environ.get(variable):
            return True
        else:
            return False

    def _set_random_state(self, seed=None):
        """
        Set Random state (seed)
        """
        if not seed:
            seed = np.random.randint(low=1, high=1E6, size=1)[0]

        np.random.seed(seed=seed)

        return seed

    def _spe(self, X):
        """
        The Unrolr (pSPE + dihedral_distance/intermolecular_distance) method itself!
        """
        alpha = self.learning_rate / float(self.n_iter)

        # Create context and queue
        ctx = cl.create_some_context()
        queue = cl.CommandQueue(ctx)

        # Compile kernel
        program = cl.Program(ctx, self._kernel).build()

        # Send dihedral angles to CPU/GPU
        X_buf = cl.Buffer(ctx, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=X)

        # Allocate space on CPU/GPU to store rij and dij
        tmp = np.zeros((X.shape[0],), dtype=np.float32)
        rij_buf = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY, tmp.nbytes)
        dij_buf = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY, tmp.nbytes)

        # Generate initial (random)
        d = np.float32(np.random.rand(self.n_components, X.shape[0]))
        # Send initial (random) embedding to the CPU/GPU
        d_buf = cl.Buffer(ctx, cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR, hostbuf=d)

        freq_progression = self.n_iter / 100.

        for i in xrange(0, self.n_iter + 1):
            if i % freq_progression == 0 and self.verbose:
                percentage = float(i) / float(self.n_iter) * 100.
                sys.stdout.write("\rUnrolr Optimization         : %8.3f %%" % percentage)
                sys.stdout.flush()

            # Choose random embedding (pivot)
            pivot = np.int32(np.random.randint(X.shape[0]))

            if self._metric == 'dihedral':
                # Compute dihedral distances
                program.dihedral_distance(queue, (X.shape[0],), None, X_buf, rij_buf, 
                                          pivot, np.int32(X.shape[1])).wait()
            elif self._metric == 'intramolecular':
                # Compute intramolecular distance
                program.intramolecular_distance(queue, (X.shape[0],), None, X_buf, rij_buf, 
                                                pivot, np.int32(X.shape[1])).wait()

            # Compute euclidean distances
            program.euclidean_distance(queue, (d.shape[1],), None, d_buf, 
                                       dij_buf, pivot, np.int32(d.shape[1]), 
                                       np.int32(d.shape[0])).wait()
            # Stochastic Proximity Embbeding
            program.spe(queue, d.shape, None, rij_buf, dij_buf, d_buf, pivot, 
                        np.int32(d.shape[1]), np.float32(self.r_neighbor), 
                        np.float32(self.learning_rate)).wait()

            self.learning_rate -= alpha

        # Get the last embedding d
        cl.enqueue_copy(queue, d, d_buf)

        if self.verbose:
            print()

        self.embedding = d

    def _evaluate_embedding(self, X):
        """
        Dirty function to evaluate the final embedding
        """
        embedding = self.embedding
        r_neighbor = self.r_neighbor

        # Creation du contexte et de la queue
        ctx = cl.create_some_context()
        queue = cl.CommandQueue(ctx)

        # On compile le kernel
        program = cl.Program(ctx, self._kernel).build()

        # Send dihedral angles and embedding on CPU/GPU
        e_buf = cl.Buffer(ctx, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=embedding)
        X_buf = cl.Buffer(ctx, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=X)

        # Allocate memory
        rij = np.zeros((X.shape[0],), dtype=np.float32)
        dij = np.zeros((X.shape[0],), dtype=np.float32)
        rij_buf = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY, rij.nbytes)
        dij_buf = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY, dij.nbytes)

        sij = np.zeros((X.shape[0],), dtype=np.float32)
        sij_buf = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY, sij.nbytes)

        tmp_correl = []
        tmp_sij_sum = 0.0
        tmp_dij_sum = 0.0

        old_stress = 999.
        old_correl = 999.

        while True:
            # Choose random conformation as pivot
            pivot = np.int32(np.random.randint(X.shape[0]))

            if self._metric == 'dihedral':
                # Dihedral distances
                program.dihedral_distance(queue, (X.shape[0],), None, X_buf, rij_buf,
                                           pivot, np.int32(X.shape[1])).wait()
            elif self._metric == 'intramolecular':
                # Dihedral distances
                program.intramolecular_distance(queue, (X.shape[0],), None, X_buf, rij_buf,
                                                pivot, np.int32(X.shape[1])).wait()

            # Euclidean distances
            program.euclidean_distance(queue, (embedding.shape[1],), None, e_buf,
                                        dij_buf, pivot, np.int32(embedding.shape[1]),
                                        np.int32(embedding.shape[0])).wait()
            # Compute part of stress
            program.stress(queue, (X.shape[0],), None, rij_buf, dij_buf, sij_buf,
                           np.float32(r_neighbor)).wait()

            # Get rij, dij and sij
            cl.enqueue_copy(queue, rij, rij_buf)
            cl.enqueue_copy(queue, dij, dij_buf)
            cl.enqueue_copy(queue, sij, sij_buf)

            # Compute current correlation
            tmp = (np.dot(rij.T, dij) / rij.shape[0]) - (np.mean(rij) * np.mean(dij))
            tmp_correl.append(tmp / (np.std(rij) * np.std(dij)))
            correl = np.mean(tmp_correl)

            # Compute current stress
            tmp_sij_sum += np.sum(sij[~np.isnan(sij)])
            tmp_dij_sum += np.sum(dij)
            stress = tmp_sij_sum / tmp_dij_sum

            # Test for convergence
            if (np.abs(old_stress - stress) < self.epsilon) and (np.abs(old_correl - correl) < self.epsilon):
                self.correlation = correl
                self.stress = stress

                break
            else:
                old_stress = stress
                old_correl = correl

    def fit(self, X):
        """
        Run the Unrolr (pSPE + didhedral distance) method
        """
        # To be sure X is a single array
        X = np.ascontiguousarray(X, dtype=np.float32)

        # Fire off SPE calculation !!
        self._spe(X)
        # Evaluation embedding
        self._evaluate_embedding(X)

        # Transpose embedding
        self.embedding = self.embedding.T

    def save(self, fname='embedding.csv', frames=None):
        """
        Save all the data
        """

        fmt = ''

        if frames is not None:
            # Add frame idx to embedding
            self.embedding = np.column_stack((frames, self.embedding))
            fmt = "%012d,"

        # Create header and format
        header = "r_neighbor %s n_iter %s" %(self.r_neighbor, self.n_iter)
        header += " stress %s correlation %s" % (self.stress, self.correlation)
        header += " seed %s" % self.random_seed
        fmt += "%.5f" + (self.n_components - 1) * ",%.5f"

        # Save final embedding to txt file
        np.savetxt(fname, self.embedding, fmt=fmt, header=header)


def main():

    parser = argparse.ArgumentParser(description="Unrolr")
    parser.add_argument("-f", "--dihedral", dest="fname", required=True,
                        action="store", type=str,
                        help="HDF5 file with dihedral angles")
    parser.add_argument("-r", "--rc", dest="r_neighbor",
                        action="store", type=float, default=1.,
                        help="neighborhood cutoff")
    parser.add_argument("-n", "--ndim", dest="n_components",
                        action="store", type=int, default=2,
                        help="number of dimension")
    parser.add_argument("-c", "--cycles", dest="n_iter",
                        action="store", type=int, default=1000,
                        help="number of cycle")
    parser.add_argument("--start", dest="start",
                        action="store", type=int, default=0,
                        help="used frames from this position")
    parser.add_argument("--stop", dest="stop",
                        action="store", type=int, default=-1,
                        help="used frames until this position")
    parser.add_argument("-skip", "--skip", dest="skip",
                        action="store", type=int, default=1,
                        help="used frames at this interval")
    parser.add_argument("-o", "--output", dest="output",
                        action="store", type=str, default="embedding.csv",
                        help="output csv file")
    parser.add_argument("-s", "--seed", dest="random_seed",
                        action="store", type=int, default=None,
                        help="If you want to reproduce spe trajectory")

    options = parser.parse_args()

    fname = options.fname
    n_iter = options.n_iter
    r_neighbor = options.r_neighbor
    n_components = options.n_components
    start = options.start
    stop = options.stop
    skip = options.skip
    output = options.output
    random_seed = options.random_seed

    X = read_dataset(fname, "dihedral_angles", start, stop, skip)

    U = Unrolr(r_neighbor, n_components, n_iter, random_seed, verbose=1)
    U.fit(X)

    print("Random seed              : %8d" % U.random_seed)
    print("Stress                   : %8.3f" % U.stress)
    print("Correlation              : %8.3f" % U.correlation)

    frames = np.arange(start, X.shape[0], skip)
    U.save(output, frames)

if __name__ == "__main__":
    main()
