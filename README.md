# beam-profiler
A program written to perform real-time laser-beam profiling using Thorlabs USB cameras. Tested with a DCC 1545M camera.

### Installation
Dependancies: 64-bit python 2 distribution, PyQt5, matplotlib, numpy, ctypes, scipy, PIL.
Install propietary 64 bit thorcam software.
Change PATH variable to point to installation location of thorcam software.

### Usage 
Continuously reads and displays images from camera with adjustable exposure.
Clicking button to calculate waist will print result to UI.

### Developer notes
Functions return 0 if successful or -1 if failed, 125 means invalid parameter.

### Changelog
Added ability to zoom and set area of interest to subset of total sensor pixels.
Added ability to record background frame (subtracted from subsequent image data).
Added ability to save image (+ background if present)
Rearranged UI.
Minor changes to labelling of axes in plots in right panel.