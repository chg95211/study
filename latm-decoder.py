#!/usr/bin/env python
# LATM decoder - ISO/IEC 14496-3
#
# E.g.:
# latm-decoder 47 FC 00 00 B0 ...
# latm-decoder 47FC0000B09080 ...

import base64
import io
import sys
from collections import defaultdict

AuEndFlag = {}
AudioObjectType = {}
CELPframeLengthTableIndex = {}
HVXCframeLengthTableIndex = {}
MuxSlotLengthBytes = {}
MuxSlotLengthCoded = {}
allStreamsSameTimeFraming = None
audioMuxVersion = None
audioMuxVersionA = None
audioObjectType = None
coreCoderDelay = None
coreFrameOffset = None
crcCheckSum = None
extensionSamplingFrequency = None
frameLength = {}
frameLengthFlag = None
frameLengthType = {}
latmBufferFullness = {}
layCIndx = {}
laySIndx = {}
numChunk = None
numLayer = None
numProgram = None
numSubFrames = None
otherDataLenBits = None
otherDataPresent = None
payload = defaultdict(list)
progCIndx = {}
progSIndx = {}
samplingFrequency = None
streamID = defaultdict(dict)
taraBufferFullness = None
useSameStreamMux = None


def AudioSpecificConfig():
	global audioObjectType
	global extensionSamplingFrequency
	global samplingFrequency
	bstart = reader.btotal
	audioObjectType = GetAudioObjectType()
	samplingFrequencyIndex = reader.readbits(4, "samplingFrequencyIndex")
	if samplingFrequencyIndex == 0xF:
		samplingFrequency = reader.readbits(24, "samplingFrequency")
	channelConfiguration = reader.readbits(4, "channelConfiguration")
	sbrPresentFlag = -1
	if audioObjectType == 5:
		extensionAudioObjectType = audioObjectType
		sbrPresentFlag = 1
		extensionSamplingFrequencyIndex = reader.readbits(4, "extensionSamplingFrequencyIndex")
		if extensionSamplingFrequencyIndex == 0xF:
			extensionSamplingFrequency = reader.readbits(24, "extensionSamplingFrequency")
		audioObjectType = GetAudioObjectType()
	else:
		extensionAudioObjectType = 0
	if audioObjectType in [1, 2, 3, 4, 6, 7, 17, 19, 20, 21, 22, 23]:
		GASpecificConfig(samplingFrequencyIndex, channelConfiguration, audioObjectType)
	elif audioObjectType in [8]:
		CelpSpecificConfig()
	elif audioObjectType in [9]:
		HvxcSpecificConfig()
	elif audioObjectType in [12]:
		TTSSpecificConfig()
	elif audioObjectType in [13, 14, 15, 16]:
		StructuredSpecificConfig()
	elif audioObjectType in [24]:
		ErrorResilientCelpSpecificConfig()
	elif audioObjectType in [25]:
		ErrorResilientHvxcSpecificConfig()
	elif audioObjectType in [26, 27]:
		ParametricSpecificConfig()
	elif audioObjectType in [28]:
		SSCSpecificConfig()
	elif audioObjectType in [32, 33, 34]:
		MPEG_1_2_SpecificConfig()
	elif audioObjectType in [35]:
		DSTSpecificConfig()
	else:
		raise ValueError("Reserved")
	if audioObjectType in [17, 19, 20, 21, 22, 23, 24, 25, 26, 27]:
		epConfig = reader.readbits(2, "epConfig")
		if epConfig == 2 or epConfig == 3:
			ErrorProtectionSpecificConfig()
		if epConfig == 3:
			directMapping = reader.readbits(1, "directMapping")
			if not directMapping:
				raise ValueError("To Be Defined")
	if extensionAudioObjectType != 5 and bits_to_decode() >= 16:
		syncExtensionType = reader.readbits(11, "syncExtensionType")
		if syncExtensionType == 0x2B7:
			extensionAudioObjectType = GetAudioObjectType()
			if extensionAudioObjectType == 5:
				sbrPresentFlag = reader.readbits(1, "sbrPresentFlag")
				if sbrPresentFlag == 1:
					extensionSamplingFrequencyIndex = reader.readbits(4, "extensionSamplingFrequencyIndex")
					if extensionSamplingFrequencyIndex == 0xF:
						extensionSamplingFrequency = reader.readbits(24, "extensionSamplingFrequency")
	return reader.btotal - bstart


def GetAudioObjectType():
	audioObjectType = reader.readbits(5, "audioObjectType")
	if audioObjectType == 31:
		audioObjectType = 32 + reader.readbits(6, "audioObjectTypeExt")
	return audioObjectType


def bits_to_decode():
	return 0


def GASpecificConfig(samplingFrequencyIndex, channelConfiguration, audioObjectType):
	global aacScalefactorDataResilienceFlag
	global aacSectionDataResilienceFlag
	global aacSpectralDataResilienceFlag
	global coreCoderDelay
	global frameLengthFlag
	global layerNr
	global layer_length
	global numOfSubFrame
	frameLengthFlag = reader.readbits(1, "frameLengthFlag")
	dependsOnCoreCoder = reader.readbits(1, "dependsOnCoreCoder")
	if dependsOnCoreCoder:
		coreCoderDelay = reader.readbits(14, "coreCoderDelay")
	extensionFlag = reader.readbits(1, "extensionFlag")
	if not channelConfiguration:
		program_config_element()
	if (audioObjectType == 6) or (audioObjectType == 20):
		layerNr = reader.readbits(3, "layerNr")
	if extensionFlag:
		if audioObjectType == 22:
			numOfSubFrame = reader.readbits(5, "numOfSubFrame")
			layer_length = reader.readbits(11, "layer_length")
		if audioObjectType in [17, 19, 20, 23]:
			aacSectionDataResilienceFlag = reader.readbits(1, "aacSectionDataResilienceFlag")
			aacScalefactorDataResilienceFlag = reader.readbits(1, "aacScalefactorDataResilienceFlag")
			aacSpectralDataResilienceFlag = reader.readbits(1, "aacSpectralDataResilienceFlag")
		extensionFlag3 = reader.readbits(1, "extensionFlag3")
		if extensionFlag3:
			raise ValueError("To Be Defined In Version 3")


def PayloadLengthInfo():
	global numChunk
	if allStreamsSameTimeFraming:
		for prog in range(numProgram + 1):
			for lay in range(numLayer + 1):
				if frameLengthType[streamID[prog][lay]] == 0:
					MuxSlotLengthBytes[streamID[prog][lay]] = 0
					tmp = 255
					while tmp == 255:
						tmp = reader.readbits(8, "tmp")
						MuxSlotLengthBytes[streamID[prog][lay]] += tmp
				elif frameLengthType[streamID[prog][lay]] in [3, 5, 7]:
					MuxSlotLengthCoded[streamID[prog][lay]] = reader.readbits(2, "MuxSlotLengthCoded")
	else:
		numChunk = reader.readbits(4, "numChunk")
		for chunkCnt in range(numChunk + 1):
			streamIndx = reader.readbits(4, "streamIndx")
			prog = progCIndx[chunkCnt] = progSIndx[streamIndx]
			lay = layCIndx[chunkCnt] = laySIndx[streamIndx]
			if frameLengthType[streamID[prog][lay]] == 0:
				MuxSlotLengthBytes[streamID[prog][lay]] = 0
				tmp = 255
				while tmp == 255:
					tmp = reader.readbits(8, "tmp")
					MuxSlotLengthBytes[streamID[prog][lay]] += tmp
				AuEndFlag[streamID[prog][lay]] = reader.readbits(1, "AuEndFlag")
			elif frameLengthType[streamID[prog][lay]] in [3, 5, 7]:
				MuxSlotLengthCoded[streamID[prog][lay]] = reader.readbits(2, "MuxSlotLengthCoded")


def PayloadMux():
	if allStreamsSameTimeFraming:
		for prog in range(numProgram + 1):
			for lay in range(numLayer + 1):
				for _ in range(MuxSlotLengthBytes[streamID[prog][lay]]):
					payload[streamID[prog][lay]].append(reader.readbits(8, "payload"))
	else:
		for chunkCnt in range(numChunk + 1):
			prog = progCIndx[chunkCnt]
			lay = layCIndx[chunkCnt]
			for _ in range(MuxSlotLengthBytes[streamID[prog][lay]]):
				payload[streamID[prog][lay]].append(reader.readbits(8, "payload"))


def ByteAlign():
	reader.readbits(reader.bcount, "byteAlign")


def AudioMuxElement(muxConfigPresent):
	global useSameStreamMux
	if muxConfigPresent:
		useSameStreamMux = reader.readbits(1, "useSameStreamMux")
		if not useSameStreamMux:
			StreamMuxConfig()
	if audioMuxVersionA == 0:
		for _ in range(numSubFrames + 1):
			PayloadLengthInfo()
			PayloadMux()
		if otherDataPresent:
			for _ in range(otherDataLenBits):
				reader.readbits(1, "otherDataBit")
	else:
		raise ValueError("To Be Defined")
	ByteAlign()


def StreamMuxConfig():
	global allStreamsSameTimeFraming
	global audioMuxVersion
	global audioMuxVersionA
	global coreFrameOffset
	global crcCheckSum
	global laySIndx
	global numLayer
	global numProgram
	global numSubFrames
	global progSIndx
	global streamID
	global taraBufferFullness
	audioMuxVersion = reader.readbits(1, "audioMuxVersion")
	if audioMuxVersion == 1:
		audioMuxVersionA = reader.readbits(1, "audioMuxVersionA")
	else:
		audioMuxVersionA = 0
	if audioMuxVersionA == 0:
		if audioMuxVersion == 1:
			taraBufferFullness = LatmGetValue()
		streamCnt = 0
		allStreamsSameTimeFraming = reader.readbits(1, "allStreamsSameTimeFraming")
		numSubFrames = reader.readbits(6, "numSubFrames")
		numProgram = reader.readbits(4, "numProgram")
		for prog in range(numProgram + 1):
			numLayer = reader.readbits(3, "numLayer")
			for lay in range(numLayer + 1):
				progSIndx[streamCnt] = prog
				laySIndx[streamCnt] = lay
				streamID[prog][lay] = streamCnt
				streamCnt += 1
				if prog == 0 and lay == 0:
					useSameConfig = 0
				else:
					useSameConfig = reader.readbits(1, "useSameConfig")
				if not useSameConfig:
					if audioMuxVersion == 0:
						AudioSpecificConfig()
					else:
						ascLen = LatmGetValue()
						ascLen -= AudioSpecificConfig()
						reader.readbits(ascLen, "fillBits")
				AudioObjectType[lay] = audioObjectType
				frameLengthType[streamID[prog][lay]] = reader.readbits(3, "frameLengthType")
				if frameLengthType[streamID[prog][lay]] == 0:
					latmBufferFullness[streamID[prog][lay]] = reader.readbits(8, "latmBufferFullness")
					if not allStreamsSameTimeFraming:
						if AudioObjectType[lay] in [6, 20] and AudioObjectType[lay - 1] in [8, 24]:
							coreFrameOffset = reader.readbits(6, "coreFrameOffset")
				elif frameLengthType[streamID[prog][lay]] == 1:
					frameLength[streamID[prog][lay]] = reader.readbits(9, "frameLength")
				elif frameLengthType[streamID[prog][lay]] in [3, 4, 5]:
					CELPframeLengthTableIndex[streamID[prog][lay]] = reader.readbits(6, "CELP")
				elif frameLengthType[streamID[prog][lay]] in [6, 7]:
					HVXCframeLengthTableIndex[streamID[prog][lay]] = reader.readbits(1, "HVXC")
		otherDataPresent = reader.readbits(1, "otherDataPresent")
		if otherDataPresent:
			if audioMuxVersion == 1:
				otherDataLenBits = LatmGetValue()
			else:
				otherDataLenBits = 0
				otherDataLenEsc = 1
				while otherDataLenEsc:
					otherDataLenBits *= 2 ** 8
					otherDataLenEsc = reader.readbits(1, "otherDataLenEsc")
					otherDataLenBits += reader.readbits(8, "otherDataLenTmp")
		crcCheckPresent = reader.readbits(1, "crcCheckPresent")
		if crcCheckPresent:
			crcCheckSum = reader.readbits(8, "crcCheckSum")
	else:
		raise ValueError("To Be Defined")


def LatmGetValue():
	bytesForValue = reader.readbits(2, "bytesForValue")
	value = 0
	for _ in range(bytesForValue + 1):
		value *= 2 ** 8
		value += reader.readbits(8, "valueTmp")
	return value


class BitReader:

	def __init__(self, stream):
		self.stream = stream
		self.accumulator = 0
		self.bcount = 0
		self.btotal = 0

	def readbit(self):
		if self.bcount == 0:
			byte = self.stream.read(1)
			if not len(byte):
				raise EOFError()
			self.accumulator = ord(byte)
			self.bcount = 8
		self.bcount -= 1
		self.btotal += 1
		return (self.accumulator >> self.bcount) & 0x01

	def readbits(self, n, name):
		v = 0
		bits = n
		while bits > 0:
			v = (v << 1) | self.readbit()
			bits -= 1
		print("{field}:{size}{pad} = {bits} => {value}".format(
			field=name,
			size=n,
			pad=" " * (28 - len(name)),
			bits=bin(v)[2:].zfill(n),
			value=v))
		return v

stream = base64.b16decode(''.join(sys.argv[1:]), True)
reader = BitReader(io.BytesIO(stream))
AudioMuxElement(1)