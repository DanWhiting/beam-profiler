from __future__ import division

import os
import sys
import numpy as np
import ctypes
import PyQt5
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QGridLayout, QToolTip, QPushButton, QSlider, QFileDialog
from PyQt5.QtGui import QIcon
from matplotlib.backends.backend_qt5agg import *
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from PIL import Image
import threading
import time

# Author - Daniel J. Whiting 

class IS_RECT(ctypes.Structure):
	_fields_ = [
		("s32X", ctypes.c_int),
		("s32Y", ctypes.c_int),
		("s32Width", ctypes.c_int),
		("s32Height", ctypes.c_int)
	]

class cameraAPI():
	def __init__(self):
		# Load DLL into memory
		PATH = r'C:\Program Files\Thorlabs\Scientific Imaging\ThorCam'
		os.environ['PATH'] = ';'.join([PATH, os.environ['PATH']])
		self.dll = ctypes.CDLL(os.path.join(PATH, 'uc480_64.dll'))

		# Raise exception if no cameras found
		number_of_cameras = ctypes.c_int(0)
		self.dll.is_GetNumberOfCameras(ctypes.pointer(number_of_cameras))
		if number_of_cameras.value < 1:
			raise RuntimeError("No camera detected!")

		# Initialise camera handle
		self.ModuleHandle = ctypes.c_int()
		self.dll.is_InitCamera(ctypes.pointer(self.ModuleHandle))

		# Set AOI to full sensor area
		rectAOI = IS_RECT()
		self.dll.is_AOI(self.ModuleHandle, 2, ctypes.pointer(rectAOI), 4 * 4)
		self.shape = (rectAOI.s32Width, rectAOI.s32Height)

		# Setting monocrome 8 bit color mode
		self.dll.is_SetColorMode(self.ModuleHandle, 6)

		# Allocate memory for images
		self.pid = ctypes.c_int()
		self.ppcImgMem = ctypes.c_char_p()
		self.dll.is_AllocImageMem(self.ModuleHandle, self.shape[0], self.shape[1], 8, ctypes.pointer(self.ppcImgMem),
								  ctypes.pointer(self.pid))
		self.dll.is_SetImageMem(self.ModuleHandle, self.ppcImgMem, self.pid)

		# Additional settings
		self.dll.is_SetExternalTrigger(self.ModuleHandle, 8)
		self.dll.is_SetHardwareGain(self.ModuleHandle, 0, 0, 0, 0)
		self.dll.is_EnableAutoExit(self.ModuleHandle, 1)

	def update_exposure_time(self, t, units='ms'):
		"""Set the exposure time."""
		IS_EXPOSURE_CMD_SET_EXPOSURE = 12
		nCommand = IS_EXPOSURE_CMD_SET_EXPOSURE
		Param = ctypes.c_double(t)
		SizeOfParam = 8
		self.dll.is_Exposure(self.ModuleHandle, nCommand, ctypes.pointer(Param), SizeOfParam)

	def get_image(self):
		# Allocate memory for image:
		img_size = self.shape[0] * self.shape[1]
		c_array = ctypes.c_char * img_size
		c_img = c_array()

		# Take one picture: wait time is waittime * 10 ms:
		waittime = ctypes.c_int(1)
		self.dll.is_FreezeVideo(self.ModuleHandle, waittime)

		# Copy image data from the driver allocated memory to the memory that we allocated.
		self.dll.is_CopyImageMem(self.ModuleHandle, self.ppcImgMem, self.pid, c_img)

		# Convert to python array
		img_array = np.frombuffer(c_img, dtype=ctypes.c_ubyte)
		img_array.shape = (self.shape[1], self.shape[0])
		return img_array.astype('int')

class AOI_rect():
	def __init__(self):
		self.xmin = 0
		self.xmax = 1280
		self.ymin = 0
		self.ymax = 1024
AOI = AOI_rect()

class main(QWidget):
	def __init__(self):
		QWidget.__init__(self)

		self.cam = cameraAPI()

		self.backgroundImage = 0
		self.activateExtra = 0
		self.continuous = 0

		self.waistListX = np.zeros(20)
		self.waistListY = np.zeros(20)

		# self.setGeometry(300, 300, 300, 220)
		self.setWindowTitle('Camera Software')
		self.setWindowIcon(QIcon('web.png'))

		# Add Matplotlib Canvas to plot ThorCam image to.
		self.fig = plt.figure(figsize=(5, 5))
		self.canvas = FigureCanvasQTAgg(self.fig)
		self.toolbar = NavigationToolbar2QT(self.canvas,None)
		
		# Add second canvas to print the histograms to.
		self.intensityFig = plt.figure(figsize=(5, 2))
		self.intensityCanvas = FigureCanvasQTAgg(self.intensityFig)

		self.waistTextBox = QLineEdit(self)
		font = self.waistTextBox.font()      # lineedit current font
		font.setPointSize(20)               # change it's size
		self.waistTextBox.setFont(font)      # set font

		Button_1 = QPushButton('Calc waist', self)
		Button_1.clicked.connect(self.calc_waists)
		Button_2 = QPushButton('Set AOI to zoom window', self)
		Button_2.clicked.connect(self.On_set_AOI)
		Button_3 = QPushButton('Zoom', self)
		Button_3.clicked.connect(self.toolbar.zoom)
		Button_4 = QPushButton('Reset AOI and zoom', self)
		Button_4.clicked.connect(self.On_reset_AOI)
		self.buttonBackground = QPushButton('Record Background', self)
		self.buttonBackground.clicked.connect(self.recordBackground)
		self.buttonSaveImage = QPushButton('Save Image', self)
		self.buttonSaveImage.clicked.connect(self.saveFileDialog)

		self.buttonContinous = QPushButton('Toggle Continuous Mode', self)
		self.buttonContinous.clicked.connect(self.toggleContinuousMode)

		ButtonShowHide = QPushButton('Toggle Graphs', self)
		ButtonShowHide.clicked.connect(self.showHide)

		self.Exposure_slider = QSlider(orientation=Qt.Horizontal, parent=self)
		self.Exposure_slider.setMinimum(1)
		self.Exposure_slider.setMaximum(100)
		self.Exposure_slider.setValue(50)
		self.On_exposure_change()
		self.Exposure_slider.valueChanged.connect(self.On_exposure_change)

		# set the layout
		layout = QGridLayout()
		# layout.addWidget(self.toolbar)
		layout.addWidget(self.buttonSaveImage, 1, 0)
		layout.addWidget(Button_1, 2, 0)
		layout.addWidget(self.buttonContinous,3,0)
		layout.addWidget(self.buttonBackground,4,0)
		layout.addWidget(self.Exposure_slider, 5, 0)
		layout.addWidget(self.canvas, 6, 0)
		layout.addWidget(self.waistTextBox, 7, 0)
		layout.addWidget(Button_3, 8, 0)
		layout.addWidget(Button_2, 9, 0)
		layout.addWidget(Button_4, 10, 0)
		layout.addWidget(ButtonShowHide, 11, 0)
		
		layout.addWidget(self.intensityCanvas, 1, 1, -1, 1)
		
		# layout.addWidget(self.button)

		self.showHide()

		self.setLayout(layout)

		self.show()

		self.run_stream = True
		self.camera_stream()
	
	def saveFileDialog(self):    
		options = QFileDialog.Options()
		options |= QFileDialog.DontUseNativeDialog
		fileName, _ = QFileDialog.getSaveFileName(self,"Save Image to...","","PNG files (*.png);;All Files (*);;Text Files (*.txt)", options=options)
		if fileName:
			img = Image.fromarray((self.imdata_full+self.backgroundImage).astype(np.uint8))
			if fileName[-4:]=='.png':
				img.save(fileName,"png")
			else:
				img.save(fileName+'.png',"png")
			if type(self.backgroundImage) != type(0):
				background = Image.fromarray(self.backgroundImage.astype(np.uint8))
				if fileName[-4:]=='.png':
					img.save(fileName[:-4]+'-bg.png',"png")
				else:
					img.save(fileName+'-bg.png',"png")
	
	def recordBackground(self):
		self.backgroundImage = self.cam.get_image()

	def toggleContinuousMode(self):
		self.continuous = (self.continuous + 1) % 2
		return

	def showHide(self):
		if self.activateExtra == 1:
			self.intensityCanvas.hide()
		else:
			self.intensityCanvas.show()
		self.activateExtra = (self.activateExtra + 1) % 2

	def On_exposure_change(self):
		new_exposure = 0.037 * 10 ** (self.Exposure_slider.value() / 23)
		self.cam.update_exposure_time(new_exposure)
	
	def On_reset_AOI(self):
		AOI.xmin = 0
		AOI.xmax = 1280
		AOI.ymin = 0
		AOI.ymax = 1024
		self.ax.set_xlim(AOI.xmin,AOI.xmax)
		self.ax.set_ylim(AOI.ymin,AOI.ymax)
	
	def On_set_AOI(self):
		AOI.ymin,AOI.ymax = self.ax.get_ylim()
		AOI.xmin,AOI.xmax = self.ax.get_xlim()
	
	def closeEvent(self, event):
		self.run_stream = False
		time.sleep(1)
		event.accept()  # let the window close

	def camera_stream(self):
		self.cam_stream_thread = threading.Timer(0, function=self.capture_image)
		self.cam_stream_thread.daemon = True
		self.cam_stream_thread.start()

	def get1DIntensity(self, axis):
		
		maxIndex = np.argmax(self.imdata)

		maxYIndex, maxXIndex = np.unravel_index(maxIndex, self.imdata.shape)

		if axis == 'v':
			oneDIntensity = self.imdata[:, maxXIndex]
		if axis == 'h':
			oneDIntensity = self.imdata[maxYIndex, :]

		return oneDIntensity, (maxYIndex, maxXIndex)

	def capture_image(self):
		# Create the matplotlib axis to display the image data
		self.ax = self.fig.add_subplot(111)

		from scipy import misc
		self.imdata = self.cam.get_image()
		#from scipy.misc import imread
		#self.imdata = imread('./gaussian.jpg')
		
		self.image = self.ax.imshow(self.imdata, vmax=255, cmap='gray', origin='lower left',extent = [AOI.xmin,AOI.xmax,AOI.ymin,AOI.ymax])

		# Create the matplotlib axis to display the histogram of intensities
		self.hax = self.intensityFig.add_subplot(311)
		self.hax.set_title('Horizontal')
		self.hdata = self.get1DIntensity('h')[0]
		self.hplot, = self.hax.plot(self.hdata, color = '0.8')
		self.hintplot, = self.hax.plot(np.zeros(np.sum(self.imdata, axis=0).shape), color = '0.5', linewidth = 3)
		self.hintfit, = self.hax.plot(np.zeros(np.sum(self.imdata, axis=0).shape), color = 'g')
		self.hax.set_ylim(0,255)

		
		self.vax = self.intensityFig.add_subplot(312)
		self.vax.set_title('Vertical')
		self.vdata = self.get1DIntensity('v')[0]
		self.vplot, = self.vax.plot(self.vdata, color = '0.8')
		self.vintplot, = self.vax.plot(np.sum(self.imdata, axis=1), color = '0.5', linewidth = 3)
		self.vintfit, = self.vax.plot(np.zeros(np.sum(self.imdata, axis=1).shape), color = 'g')
		self.vax.set_ylim(0,255)

		# Create axis to display waists
		self.wax = self.intensityFig.add_subplot(313)
		self.wax.set_title('Previous 20 Waists')

		self.wxplot, = self.wax.plot(self.waistListX)
		self.wyplot, = self.wax.plot(self.waistListY)

		while self.run_stream:
			self.imdata_full = self.cam.get_image()-self.backgroundImage
			self.image.set_data(self.imdata_full)
			
			maxIndex = np.argmax(self.imdata_full)
			self.imdata = self.imdata_full[int(AOI.ymin):int(AOI.ymax),int(AOI.xmin):int(AOI.xmax)]
			self.hdata = self.get1DIntensity('h')[0]
			self.vdata = self.get1DIntensity('v')[0]
			
			self.hplot.set_xdata(np.arange(0,len(self.hdata)))
			self.vplot.set_xdata(np.arange(0,len(self.vdata)))
			self.hplot.set_ydata(self.hdata)
			self.vplot.set_ydata(self.vdata)
			
			vint = np.sum(self.imdata, axis=1).astype(np.float64) # Sum of pixel values in horizontal direction
			hint = np.sum(self.imdata, axis=0).astype(np.float64) # Sum of pixel values in vertical direction
			
			vint *= 255/vint.max()
			hint *= 255/hint.max()
			
			self.hintplot.set_xdata(np.arange(0,len(hint)))
			self.vintplot.set_xdata(np.arange(0,len(vint)))
			self.hintplot.set_ydata(hint)
			self.vintplot.set_ydata(vint)
			
			self.wxplot.set_xdata(np.arange(0,len(self.waistListX)))
			self.wyplot.set_xdata(np.arange(0,len(self.waistListY)))
			self.wxplot.set_ydata(self.waistListX)
			self.wyplot.set_ydata(self.waistListY)
			
			self.hax.set_xlim(0,len(self.hdata))
			self.vax.set_xlim(0,len(self.vdata))

			if self.continuous ==1:
				self.calc_waists()

			self.wax.relim()
			self.wax.autoscale_view(True, True, True)


			self.canvas.draw()
			self.intensityCanvas.draw()

			self.canvas.flush_events()
			self.intensityCanvas.flush_events()
			self.intensityFig.tight_layout()

	def gaussian(self,x, a, x0, b, wx):
		a = np.abs(a)
		return a * np.exp(-2*((x - x0) / wx) ** 2)+ b

	def calc_waists(self):
		try:
			xdata = np.sum(self.imdata, axis=0)  # x
			ydata = np.sum(self.imdata, axis=1)  # x
			
			xaxis = np.arange(len(xdata))
			yaxis = np.arange(len(ydata))

			p0x = (xdata.max(), xdata.argmax(), 0, (AOI.xmax-AOI.xmin)/5)
			p0y = (ydata.max(), ydata.argmax(), 0, (AOI.ymax-AOI.ymin)/5)

			px, covx = curve_fit(self.gaussian, xaxis, xdata,
						   p0=p0x)
			py, covy = curve_fit(self.gaussian, yaxis, ydata,
						   p0=p0y)
						 
			hfit = self.gaussian(xaxis, *px)
			vfit = self.gaussian(yaxis, *py)
						 
			hfit *= 255./hfit.max()
			vfit *= 255./vfit.max()
			
			self.hintfit.set_ydata(hfit)
			self.vintfit.set_ydata(vfit)
			self.hintfit.set_xdata(np.arange(0,len(hfit)))
			self.vintfit.set_xdata(np.arange(0,len(vfit)))

			wx = np.abs(px[-1])
			wy = np.abs(py[-1])


			pixel_size = 5.2e-3  # mm

			self.waistListX = np.roll(self.waistListX, 1)
			self.waistListY = np.roll(self.waistListY, 1)
			self.waistListX[0] = wx * pixel_size
			self.waistListY[0] = wy * pixel_size

			message = 'wx = %.4f | wy = %.4f (mm)' % (wx*pixel_size,wy*pixel_size)
			self.waistTextBox.setText(message)
		except Exception as e:
			print( e )
			None


if __name__ == '__main__':
	app = QApplication(sys.argv)
	main = main()
sys.exit(app.exec_())