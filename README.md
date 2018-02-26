[![DOI](https://zenodo.org/badge/59756594.svg)](https://zenodo.org/badge/latestdoi/59756594)

# Unrolr
Conformational analysis of MD trajectories based on (pivot-based) Stochastic Proximity Embedding using dihedral distance as a metric. 

## Prerequisites

You need, at a minimum (requirements.txt):

* Python 2.7
* NumPy
* H5py
* Pandas
* Matplotlib
* PyOpenCL
* MDAnalysis (==0.15)

## Installation on UNIX

I highly recommand you to install the Anaconda distribution (https://www.continuum.io/downloads) if you want a clean python environnment with nearly all the prerequisites already installed (NumPy, H5py, Pandas, Matplotlib).

1 . First, you have to install OpenCL:
* MacOS: Good news, you don't have to install OpenCL, it works out-of-the-box. 
* AMD: From all the tutorials you can find on the internet, this one it is still the more succinct one that I found: [AMD OpenCL installation on Ubuntu](https://ethereum.gitbooks.io/frontier-guide/content/gpu.html). 
* Nvidia: You can either install the [CUDA toolkit](https://developer.nvidia.com/cuda-downloads) or directly the package ```nvidia-opencl-dev```.
* Intel: And of course it's working also on CPU just by installing this [runtime software package](https://software.intel.com/en-us/articles/opencl-drivers). 

2 . As a final step, 
```bash
# Get the package
wget https://github.com/jeeberhardt/unrolr/archive/master.zip
unzip unrolr-master.zip
rm unrolr-master.zip
cd unrolr-master

# Install the package
python setup.py install
```

If somehow pip is having problem to install all the dependencies,
```bash
conda config --append channels conda-forge
conda install pyopencl
pip install mdanalysis==0.15

# Try again
python setup.py install
```

## OpenCL context

Before running Unrolr, you need to define the OpenCL context. And it is a good way to see if everything is working correctly.

```bash
python -c 'import pyopencl as cl; cl.create_some_context()'
```

Here in my example, I have the choice between 3 differents computing device (2 graphic cards and one CPU). 

```bash
Choose platform:
[0] <pyopencl.Platform 'AMD Accelerated Parallel Processing' at 0x7f97e96a8430>
Choice [0]:0
Choose device(s):
[0] <pyopencl.Device 'Tahiti' on 'AMD Accelerated Parallel Processing' at 0x1e18a30>
[1] <pyopencl.Device 'Tahiti' on 'AMD Accelerated Parallel Processing' at 0x254a110>
[2] <pyopencl.Device 'Intel(R) Core(TM) i7-3820 CPU @ 3.60GHz' on 'AMD Accelerated Parallel Processing' at 0x21d0300>
Choice, comma-separated [0]:1
Set the environment variable PYOPENCL_CTX='0:1' to avoid being asked again.
```

Now you can set the environment variable.

```bash
export PYOPENCL_CTX='0:1'
```

## Example

```python
from unrolr import Unrolr
from unrolr.feature_extraction import calpha_dihedrals
from unrolr.utils import save_dataset


top_file = 'examples/inputs/villin.psf'
trj_file = 'examples/inputs/villin.dcd'

# Extract all calpha dihedral angles from trajectory and store them into a HDF5 file
X = calpha_dihedrals(top_file, trj_file)
save_dataset('dihedral_angles.h5', "dihedral_angles", X)

# Fit X using Unrolr (pSPE + dihedral distance) and save the embedding into a csv file
U = Unrolr(r_neighbor=0.27, n_iter=50000, verbose=1)
U.fit(X)
U.save()

print U.stress, U.correlation
```

## Todo list
- [ ] Compatibility with python 3
- [ ] Compatibility with the latest version of MDAnalysis
- [ ] Unit tests
- [ ] Accessible directly from pip
- [ ] Improve dihedral distance metric sensibility
- [ ] Improve OpenCL performance (global/local memory)

## Citation
Jérôme Eberhardt, Roland H. Stote, and Annick Dejaegere. (soon) *Unrolr: structural analysis of protein conformations using Stochastic Proximity Embedding.*

## License
MIT
