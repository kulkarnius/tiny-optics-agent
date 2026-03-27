import time
from ctypes import *


class pdxc:

    pdxcLib = None
    isLoad = False

    @staticmethod
    def ListDevices():
        """List all connected pdxc devices
        Returns:
           The pdxc device list, each deice item is serialNumber/COM
        """
        str1 = create_string_buffer(10240)
        result = pdxc.pdxcLib.List(str1, 10240)
        devicesStr = str1.value.decode("utf-8", "ignore").rstrip('\x00').split(',')
        length = len(devicesStr)
        i = 0
        devices = []
        devInfo = ["", ""]
        while i < length:
            str2 = devicesStr[i]
            if i % 2 == 0:
                if str2 != '':
                    devInfo[0] = str2
                else:
                    i += 1
            else:
                devInfo[1] = str2
                devices.append(devInfo.copy())
            i += 1
        return devices

    @staticmethod
    def load_library(path):
        pdxc.pdxcLib = cdll.LoadLibrary(path)
        pdxc.isLoad = True

    def __init__(self):
        lib_path = "C:/Program Files (x86)/Thorlabs/PDXC/Sample/Thorlabs_PDXC_PythonSDK/PDXC_COMMAND_LIB_win64.dll"
        if not pdxc.isLoad:
            pdxc.load_library(lib_path)
        self.hdl = -1

    def Open(self, serialNo, nBaud, timeout):
        """Open device
        Args:
            serialNo: serial number of pdxc device
            nBaud: bit per second of port
            timeout: set timeout value in (s)
        Returns:
            non-negative number: hdl number returned Successful; negative number: failed.
        """
        ret = -1
        if pdxc.isLoad:
            ret = pdxc.pdxcLib.Open(serialNo.encode('utf-8'), nBaud, timeout)
            if ret >= 0:
                self.hdl = ret
            else:
                self.hdl = -1
        return ret

    def IsOpen(self, serialNo):
        """Check opened status of device
        Args:
            serialNo: serial number of device
        Returns:
            0: device is not opened; 1: device is opened; negative number : failed.
        """
        ret = -1
        if pdxc.isLoad:
            ret = pdxc.pdxcLib.IsOpen(serialNo.encode('utf-8'))
        return ret

    def GetHandle(self, serialNo):
        """Get handle of port
        Args:
            serialNo: serial number of the device to be checked.
        Returns:
            0: -1:no handle  non-negtive number: handle.
        """
        ret = -1
        if pdxc.isLoad:
            ret = pdxc.pdxcLib.GetHandle(serialNo.encode('utf-8'))
        return ret

    def Close(self):
        """Close opened device
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            ret = pdxc.pdxcLib.Close(self.hdl)
        return ret

    def GetCurrentStatus(self, secondary, status):
        """In D - sub Mode, it will return strings consist of ERR, KP, KI, KD, Current Loop, Velocity Level(open loop),
        Step size(open loop), Speed(Closed loop), Jog Step(closed loop), Home Flag and Abnormal Detection Status,
        parameters in one command, results will be separated by ',' for each segment. In SMC Mode, it will return
        strings consist of ERR, Velocity and Step Size for Channel 1, Velocity and Step Size for channel 2.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            status: device status
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            sta = create_string_buffer(1024)
            ret = pdxc.pdxcLib.Get_CurrentStatus(self.hdl, secondary, sta)
            status[0] = sta.value.decode("utf-8", "ignore").rstrip('\x00').replace(">\r\n", "")
        return ret

    def GetSN(self, secondary, SN):
        """Get the SN of PDXC controller.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            SN: PDXC controller SN
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            s = create_string_buffer(1024)
            ret = pdxc.pdxcLib.Get_SN(self.hdl, secondary, s)
            SN[0] = s.value.decode("utf-8", "ignore").rstrip('\x00').replace("\r\n", "")
        return ret

    def GetSN2(self, secondary, SN2):
        """Get the Serial-Number followed by Item-Number of stage connected to PDXC controller, with the former one
        consist of strictly 8 bytes, and the latter one is not definte(e.g. when we get "SN024680PDX1/M", "SN024680"
        represent SN, "PDX1/M" represent Item-Number.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            SN2: Serial-Number and Item-Number of stage
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            s2 = create_string_buffer(1024)
            ret = pdxc.pdxcLib.Get_SN2(self.hdl, secondary, s2)
            SN2[0] = s2.value.decode("utf-8", "ignore").rstrip('\x00').replace("\r\n", "")
        return ret

    def GetFV(self, secondary, fv):
        """Get strings, with former one is firmware version, the latter one is hardware version, the two are
        seperated by comma ','
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            fv: firmware version and hardware version
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            f = create_string_buffer(1024)
            ret = pdxc.pdxcLib.Get_FV(self.hdl, secondary, f)
            fv[0] = f.value.decode("utf-8", "ignore").rstrip('\x00').replace("\r\n", "")
        return ret

    def GetCalibrationIsCompleted(self, secondary, homed):
        """Get 'YES' when calibration complete, 'NO' when not
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            homed: device calibration completed status
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            ho = create_string_buffer(64)
            ret = pdxc.pdxcLib.Get_CalibrationIsCompleted(self.hdl, secondary, ho)
            homed[0] = ho.value.decode("utf-8", "ignore").rstrip('\x00')
        return ret

    def GetDaisyChainStatus(self, secondary, status):
        """Get the current status, these are "Single-Mode", "Chain-Mode Main", "Chain-Mode Secondary1",
        "Chain-Mode Secondary2", .. "Chain-Mode Secondary8". Daisy - chain query command format is as following,
        M0:<CMD ? >_Sx : <CMD ? >_Sy : <CMD ? ><CR> M0 means the fixed Main, while Sx means x - th Secondary, x starts
        from 1 to 11. <CMD ? > means listed Query, eg.POS ?, and the return code is begin with "Sx:".
        Args:
            secondary: index in daisy chain (0:Single Mode, 1:Main, 2 -12 : Secondary1 - Secondary11)
            status: current Daisy - chain status
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            sta = c_byte(0)
            ret = pdxc.pdxcLib.Get_DaisyChainStatus(self.hdl, secondary, byref(sta))
            status[0] = sta.value
        return ret

    def GetUserDataIsSaved(self, secondary, saved):
        """Get data saved status
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            saved: saved status(bit 0 : close - loop stage, bit 1 : SMC stages)
                   0 : no user data at all
                   1 : only close - loop stage
                   2 : only SMC stages
                   3 : both close - loop and SMC stages
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            sav = create_string_buffer(1024)
            ret = pdxc.pdxcLib.Get_UserDataIsSaved(self.hdl, secondary, sav)
            saved[0] = sav.value.decode("utf-8", "ignore").rstrip('\x00').replace(">\r\n", "")
        return ret

    def GetKpOfPidParameters(self, secondary, Kp):
        """Get current Kp value
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            Kp: Kp of PID
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            p = c_double(0)
            ret = pdxc.pdxcLib.Get_KpOfPidParameters(self.hdl, secondary, byref(p))
            Kp[0] = p.value
        return ret

    def GetKiOfPidParameters(self, secondary, Ki):
        """Get current Ki value
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            Ki: Ki of PID
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            i = c_double(0)
            ret = pdxc.pdxcLib.Get_KiOfPidparameters(self.hdl, secondary, byref(i))
            Ki[0] = i.value
        return ret

    def GetKdOfPidParameters(self, secondary, Kd):
        """Get current Kd value
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            Kd: Kd of PID
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            d = c_double(0)
            ret = pdxc.pdxcLib.Get_KdOfPidparameters(self.hdl, secondary, byref(d))
            Kd[0] = d.value
        return ret

    def GetOpenLoopFrequency(self, secondary, fry):
        """Get current frequency of open loop of channel 1 in SMC mode.The unit is Hz
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            fry: current frequency of open loop
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            fr = c_int(0)
            ret = pdxc.pdxcLib.Get_OpenLoopFrequency(self.hdl, secondary, byref(fr))
            fry[0] = fr.value
        return ret

    def GetOpenLoopFrequency2(self, secondary, fry2):
        """Get current frequency of open loop of channel 2 in SMC mode.The unit is Hz
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            fry2: current frequency of open loop
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            fr2 = c_int(0)
            ret = pdxc.pdxcLib.Get_OpenLoopFrequency2(self.hdl, secondary, byref(fr2))
            fry2[0] = fr2.value
        return ret

    def GetOpenLoopFrequency3(self, secondary, fry3):
        """Get current frequency of open loop for PD2/PD3.The unit is Hz.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            fry3: current frequency of open loop
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            fr3 = c_int(0)
            ret = pdxc.pdxcLib.Get_OpenLoopFrequency3(self.hdl, secondary, byref(fr3))
            fry3[0] = fr3.value
        return ret

    def GetLoopStatus(self, secondary, loop):
        """Get device loop status
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            loop: loop status(1 :open loop, 0 :close loop)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            lo = c_int(0)
            ret = pdxc.pdxcLib.Get_LoopStatus(self.hdl, secondary, byref(lo))
            loop[0] = lo.value
        return ret

    def GetAbnormalMoveDetect(self, secondary, enable):
        """Get whether abnormal move detect enable
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            enable: ('1' : enabled, '0' : disabled)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            enab = c_int(0)
            ret = pdxc.pdxcLib.Get_AbnormalMoveDetect(self.hdl, secondary, byref(enab))
            enable[0] = enab.value
        return ret

    def GetErrorMessage(self, secondary, error):
        """Get error message code
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            error: error code
                   0 : None errors occurred,
                   1 : command not defined,
                   2 : command Data out - of - range,
                   3 : device failed to execute last command,
                   4 : no waveform data loaded,
                   5 : Stage need Home first,
                   6 : device works in the wrong mode,
                   7 : stage move abnormal,
                   8  : excessive current occurred,
                   9 : over temperature occurred,
                   17 : unkown error occurred)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            err = c_int(0)
            ret = pdxc.pdxcLib.Get_ErrorMessage(self.hdl, secondary, byref(err))
            error[0] = err.value
        return ret

    def GetCurrentPosition(self, secondary, position):
        """Get current position counter.It only returns position value in D - SUB mode, other will return warnings
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            position: current position: PDX1/PDX1A/PDX1AV/PDX1D/PDX1DV[-10,10]mm; PDX2[-2.5,2.5]mm; PDX3[-25,25]mm;
            PDX4[-6,6]mm; PDXZ1[-2.25,2.25]mm; PDXR:[-999.9,999.9]°; PDXG1[-8,8]°
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            posi = c_double(0)
            ret = pdxc.pdxcLib.Get_CurrentPosition(self.hdl, secondary, byref(posi))
            position[0] = posi.value
        return ret

    def GetTargetTriggerPosition(self, secondary, position):
        """Get the target position which is calculated based on Analog In Gain and Analog In Offset.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            position: target position: PDX1/PDX1A/PDX1AV/PDX1D/PDX1DV[-10,10]mm; PDX2[-2.5,2.5]mm;
            PDX3[-25,25]mm; PDX4[-6,6]mm; PDXZ1[-2.25,2.25]mm; PDXR:[-999.9,999.9]°; PDXG1[-8,8]°
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            tarposi = c_double(0)
            ret = pdxc.pdxcLib.Get_TargetTriggerPosition(self.hdl, secondary, byref(tarposi))
            position[0] = tarposi.value
        return ret

    def GetDisabled(self, secondary, disable):
        """Get device disable state, under disable state stage will not move.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            disable: disable state( 0 :enabled, 1 :disabled)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            disab = c_int(0)
            ret = pdxc.pdxcLib.Get_Disabled(self.hdl, secondary, byref(disab))
            disable[0] = disab.value
        return ret

    def GetOpenLoopJogSize(self, secondary, stepsize):
        """Get the step size for open - loop for Channel 1
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            stepsize: open loop jog step size (1~65535)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            steps = c_int(0)
            ret = pdxc.pdxcLib.Get_OpenLoopJogSize(self.hdl, secondary, byref(steps))
            stepsize[0] = steps.value
        return ret

    def GetOpenLoopJogSize2(self, secondary, stepsize2):
        """Get the step size for open - loop for Channel 2
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            stepsize2: open loop jog step size (1~65535)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            steps2 = c_int(0)
            ret = pdxc.pdxcLib.Get_OpenLoopJogSize2(self.hdl, secondary, byref(steps2))
            stepsize2[0] = steps2.value
        return ret

    def GetOpenLoopJogSize3(self, secondary, stepsize3):
        """Get the step size for open - loop for PD2/PD3
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            stepsize3: open loop jog step size (1~65535)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            steps3 = c_int(0)
            ret = pdxc.pdxcLib.Get_OpenLoopJogSize3(self.hdl, secondary, byref(steps3))
            stepsize3[0] = steps3.value
        return ret

    def GetForwardAmplitude(self, secondary, forampli):
        """Get the forward amplitude for PD2/PD3/SMC
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            forampli: forward amplitude (10~100)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            fa = c_int(0)
            ret = pdxc.pdxcLib.Get_ForwardAmplitude(self.hdl, secondary, byref(fa))
            forampli[0] = fa.value
        return ret

    def GetBackwardAmplitude(self, secondary, baampli):
        """Get the backward amplitude for PD2/PD3/SMC
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            baampli: backward amplitude (10~100)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            ba = c_int(0)
            ret = pdxc.pdxcLib.Get_BackwardAmplitude(self.hdl, secondary, byref(ba))
            baampli[0] = ba.value
        return ret

    def GetSpeedStageType(self, secondary, type):
        """Get the current type of stage
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            type: stage type(0 :PDX1/PDX2/PDX3/PDX4/PDXR/PDXZ1/PDX1A/PDX1AV/PDX1D/PDX1DV/PDXG1 stage, 1 :SMC stage,
            2 :PD2/PD3 stage)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            ty = c_int(0)
            ret = pdxc.pdxcLib.Get_SpeedStageType(self.hdl, secondary, byref(ty))
            type[0] = ty.value
        return ret

    def GetAllParametersInExternalTrigger(self, secondary, alltriggerState):
        """Get all parameters except for Manual mode which has no parameters, they are "AR/AF,FR/FF[value],PR/PF[pos1],
        PR/PF[pos2]", which stands for Analog - In mode with rising / falling edge, Fixed - Size mode with
        rising / falling edge and value defined in PDX1/PDX2/PDX3/PDX4/PDXZ1/PDX1A/PDX1AV/PDX1D/PDX1DV(mm)/PDXR/PDXG1(°)
         unit, and Two - Position - Switching mode with rising / falling for each position, assigned by pos1 and pos2.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            alltriggerState: device all trigger State
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            alltrigSta = create_string_buffer(1024)
            ret = pdxc.pdxcLib.Get_AllParametersInExternalTrigger(self.hdl, secondary, alltrigSta)
            alltriggerState[0] = alltrigSta.value.decode("utf-8", "ignore").rstrip('\x00').replace(">\r\n", "")
        return ret

    def GetCurrentStatusInExternalTrigger(self, secondary, triggerState):
        """Get the current status of external trigger mode, they are "ML"(Manual mode), "AR/AF"(Analog-In mode with
        rising/falling edge), "FR/FF[value]"(Fixed-Step size mode), and "PR/PF[pos1],PR/PF[pos2]"(Two-Postion Switching
        mode).
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            triggerState: status of external trigger mode
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            trigSta = create_string_buffer(1024)
            ret = pdxc.pdxcLib.Get_CurrentStatusInExternalTrigger(self.hdl, secondary, trigSta)
            triggerState[0] = trigSta.value.decode("utf-8", "ignore").rstrip('\x00').replace(">\r\n", "")
        return ret

    def GetAnalogInputGain(self, secondary, aiGain):
        """Get gain value of analog input
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            aiGain: analog input gain,the range is: PDX1/PDX2/PDX3/PDX4/PDXZ1/PDX1A/PDX1AV/PDX1D/PDX1DV:[0.1,1];
                PDXR1:[0.1,100]; PDXG1:[0.1,1]
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            aiG = c_double(0)
            ret = pdxc.pdxcLib.Get_AnalogInputGain(self.hdl, secondary, byref(aiG))
            aiGain[0] = aiG.value
        return ret

    def GetAnalogInputOffSet(self, secondary, aiOffSet):
        """Get OffSet value of analog input
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            aiOffSet: analog input offset:PDX1/PDX1A/PDX1AV/PDX1D/PDX1DV:[-10,10]mm; PDX2:[-2.5,2.5]mm; PDX3[-25,25]mm;
            PDX4[-6,6]mm; PDXZ1[-2.25,2.25]mm; PDXR:[-999.9,999.9]°; PDXG1:[-8,8]°.
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            aiO = c_double(0)
            ret = pdxc.pdxcLib.Get_AnalogInputOffSet(self.hdl, secondary, byref(aiO))
            aiOffSet[0] = aiO.value
        return ret

    def GetAnalogOutGain(self, secondary, aoGain):
        """Get gain value of analog output
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            aoGain: analog output gain,the range is [0.1,1]V
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            aoG = c_double(0)
            ret = pdxc.pdxcLib.Get_AnalogOutGain(self.hdl, secondary, byref(aoG))
            aoGain[0] = aoG.value
        return ret

    def GetAnalogOutOffSet(self, secondary, aoOffSet):
        """Get OffSet value of analog output
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            aoOffSet: analog output offset:PDX1/PDX2/PDX3/PDX4/PDX1A/PDX1AV/PDX1D/PDX1DV:[-10,10]mm;
                PDXZ1:[-2.25,2.25]mm; PDXR:[-999.9,999.9]°; PDXG1:[-8,8]°
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            aoO = c_double(0)
            ret = pdxc.pdxcLib.Get_AnalogOutOffSet(self.hdl, secondary, byref(aoO))
            aoOffSet[0] = aoO.value
        return ret

    def GetPositionLimit(self, secondary, limit):
        """Get values of positon limit by format of [Min, Max].
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            limit: Positon limit. Format of [Min, Max]
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            lim = create_string_buffer(1024)
            ret = pdxc.pdxcLib.Get_PositionLimit(self.hdl, secondary, lim)
            limit[0] = lim.value.decode("utf-8", "ignore").rstrip('\x00').replace("\n>\r\n", "")
        return ret

    def GetJoystickStatus(self, secondary, number):
        """Get the joystick status.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main)
            number: The number of knob on joystick. 0: No joystick is connected to the device
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            numb = c_int(0)
            ret = pdxc.pdxcLib.Get_JoystickStatus(self.hdl, secondary, byref(numb))
            number[0] = numb.value
        return ret

    def GetJoystickConfig(self, secondary, value):
        """Get the config of joystick
        Args:
            secondary: index in daisy chain (0:Single Mode or Main)
            value: Return the array of X,Y,x=0 means no device, x=1 means Single-Mode or Main, x=2 to 12 means
                   Secondary1 to Secondary11, y means the number of knob on joystick(from 1 to n),each group of data is
                   separated by space such as "[1,1  2,2  4,3]".
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            val = create_string_buffer(1024)
            ret = pdxc.pdxcLib.Get_JoystickConfig(self.hdl, secondary, val)
            value[0] = val.value.decode("utf-8", "ignore").rstrip('\x00').replace("\n>\r\n", "")
        return ret

    def GetInitPosition(self, secondary, value):
        """Get init position state
        Args:
            secondary: index in daisy chain (0:Single Mode or Main)
            value: Return init position state(0:stages will keep motionless when controller powered on, 1:stages will
            return to the last saved position when powered on)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            val = c_int(0)
            ret = pdxc.pdxcLib.Get_InitPosition(self.hdl, secondary, byref(val))
            value[0] = val.value
        return ret

    def SetDaisyChain(self, index):
        """Set device position in daisy-chain.
        Args:
            index: index in daisy chain (0:Single Mode, 1:Main, 2 -12 : Secondary1 - Secondary11)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            ind = c_int(index)
            ret = pdxc.pdxcLib.Set_DaisyChain(self.hdl, ind)
        return ret

    def SetTargetSpeed(self, secondary, speed):
        """Set the desired speed. Work only under D- SUB mode, other will return warnings.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            speed: desired speed(PDX1:2-20 mm/s; PDXZ1/PDX1A/PDX1AV:1 mm/s; PDX1D/PDX1DV:1-10 mm/s; PDX2/PDX3:1-10 mm/s;
                PDX4:1-15 mm/s; PDXR:10-30 °/s; PDXG1:1-5 °/s).
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            sp = c_int(speed)
            ret = pdxc.pdxcLib.Set_TargetSpeed(self.hdl, secondary, sp)
        return ret

    def SetOpenLoopFrequency(self, secondary, fry):
        """Set the open loop frequency of channel 1.The unit is Hz. Must in SMC mode
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            fry: current frequency of open loop
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            fr = c_int(fry)
            ret = pdxc.pdxcLib.Set_OpenLoopFrequency(self.hdl, secondary, fr)
        return ret

    def SetOpenLoopFrequency2(self, secondary, fry2):
        """Set the open loop frequency of channel 2.The unit is Hz. Must in SMC mode
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            fry2: current frequency of open loop
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            fr2 = c_int(fry2)
            ret = pdxc.pdxcLib.Set_OpenLoopFrequency2(self.hdl, secondary, fr2)
        return ret

    def SetOpenLoopFrequency3(self, secondary, fry3):
        """Set the output frequency of D-Sub stage without encoder(PD2).The unit is Hz.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            fry3: current frequency of open loop
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            fr3 = c_int(fry3)
            ret = pdxc.pdxcLib.Set_OpenLoopFrequency3(self.hdl, secondary, fr3)
        return ret

    def SetOpenLoopJogSize(self, secondary, stepsize):
        """Set the step size for open - loop for Channel 1
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            stepsize: open loop jog step size (1~65535)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            st = c_int(stepsize)
            ret = pdxc.pdxcLib.Set_OpenLoopJogSize(self.hdl, secondary, st)
        return ret

    def SetOpenLoopJogSize2(self, secondary, stepsize2):
        """Set the step size for open - loop for Channel 2
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            stepsize2: open loop jog step size (1~65535)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            st2 = c_int(stepsize2)
            ret = pdxc.pdxcLib.Set_OpenLoopJogSize2(self.hdl, secondary, st2)
        return ret

    def SetOpenLoopJogSize3(self, secondary, stepsize3):
        """Set the step size for open - loop for PD2/PD3
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            stepsize3: open loop jog step size (1~400000)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            st3 = c_int(stepsize3)
            ret = pdxc.pdxcLib.Set_OpenLoopJogSize3(self.hdl, secondary, st3)
        return ret

    def SetForwardAmplitude(self, secondary, forampli):
        """Set the forward amplitude for PD2/SMC
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            forampli: forward amplitude (10~100)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            forward = c_int(forampli)
            ret = pdxc.pdxcLib.Set_ForwardAmplitude(self.hdl, secondary, forward)
        return ret

    def SetBackwardAmplitude(self, secondary, baampli):
        """Set the forward amplitude for PD2/PD3/SMC
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            baampli: forward amplitude (10~100)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            backward = c_int(baampli)
            ret = pdxc.pdxcLib.Set_BackwardAmplitude(self.hdl, secondary, backward)
        return ret

    def SetPositionCalibration(self, secondary, home):
        """Calibrate the QDEC counter after power - up.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            home: controller home(1: Yes, 0:No)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            ho = c_int(home)
            ret = pdxc.pdxcLib.Set_PositionCalibration(self.hdl, secondary, ho)
            time.sleep(10)
        return ret

    def SetAbnormalMoveDetect(self, secondary, enable):
        """Switch on or off the abnormal move detection, default is on.Used to detect stage stuck or move by external
        force.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            enable: detect enable(1 : Enable , 0 :Disable)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            en = c_int(enable)
            ret = pdxc.pdxcLib.Set_AbnormalMoveDetect(self.hdl, secondary, en)
        return ret

    def SetLoop(self, secondary, loop):
        """Switch closeloop and open loop
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            loop: loop type (1 : open loop (default), 0 : close loop.)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            lo = c_int(loop)
            ret = pdxc.pdxcLib.Set_Loop(self.hdl, secondary, lo)
        return ret

    def SetTargetPosition(self, secondary, position):
        """Set the target position counter.Only work in Manual Mode.
        In Open Loop, will use continuous pulses at preset amplitude until reach the destination without PID
        control(including Speed and Acurate position).
        Work in both Open and Closed Loop in D - SUB mode only.
        While in Closed Loop, will add PID control, and anlaog move near destination.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            position: Target Position: PDX1/PDX1A/PDX1AV/PDX1D/PDX1DV[-10,10]mm; PDX2[-2.5,2.5]mm; PDX3[-25,25]mm;
            PDX4[-6,6]mm; PDXZ1[-2.25,2.25]mm; PDXR:[-180,180]°; PDXG1[-8,8]°.
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            po = c_double(position)
            ret = pdxc.pdxcLib.Set_TargetPosition(self.hdl, secondary, po)
        return ret

    def SetKpOfPidParameters(self, secondary, Kp):
        """Set current Kp value, will store in Flash memory.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            Kp: Kp of PID
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            Kpva = c_double(Kp)
            ret = pdxc.pdxcLib.Set_KpOfPidParameters(self.hdl, secondary, Kpva)
        return ret

    def SetKiOfPidParameters(self, secondary, Ki):
        """Set current Ki value, will store in Flash memory.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            Ki: Ki of PID
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            Kiva = c_double(Ki)
            ret = pdxc.pdxcLib.Set_KiOfPidParameters(self.hdl, secondary, Kiva)
        return ret

    def SetKdOfPidParameters(self, secondary, Kd):
        """Set current Kd value, will store in Flash memory.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            Kd: Kd of PID
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            Kdva = c_double(Kd)
            ret = pdxc.pdxcLib.Set_KdOfPidParameters(self.hdl, secondary, Kdva)
        return ret

    def SetAnalogInputGain(self, secondary, aiGain):
        """Change gain value of analog input, default input voltage range is[-10V, 10V], standing for
        PDX1/PDX1A/PDX1AV/PDX1D/PDX1DV[+ -10mm]/PDX2[+ -2.5mm]/PDX3[+ -25mm]/PDX4[+ -6mm]/PDXZ1[+-2.25mm]
        /PDXR[+ - 999.9°]/PDXG1[+ -8°] position range.
        If change value of Gain&Offset, we will get new input voltage range.The analog input gain vaule(ING),
        calculated by(max - min) / 20, analog input offSet value(INO) calculated by(min + max) / 2. E.g.If new wanted
        input range is in[0V, 5V], which means analog input gain is 0.25, analog input offSet value is 2.5.
        (the new Voltage Sampled is function of Vold, ING and INO Vnew = ING * Vold + 1.5(1 - ING) - 0.15*INO,
        where Vout is default range's output.)
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            aiGain: gain value of analog input,the range is: PDX1/PDX2/PDX3/PDX4/PDXZ1/PDX1A/PDX1AV/PDX1D/PDX1DV:[0.1,1];
                    PDXR1:[0.1,100]; PDXG1:[0.1,1].
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            aiG = c_double(aiGain)
            ret = pdxc.pdxcLib.Set_AnalogInputGain(self.hdl, secondary, aiG)
        return ret

    def SetAnalogInputOffSet(self, secondary, aiOffset):
        """Change offset value of analog input, default input voltage range is[-10V, 10V], standing for
        PDX1/PDX1A/PDX1AV/PDX1D/PDX1DV[+ -10mm]/PDX2[+ -2.5mm]/PDX4[+ -6mm]/PDXZ1[+-2.25mm]/PDXR[+ - 999.9°]
        /PDXG1[+ -8°] position range.
        If change value of Gain&Offset, we will get new input voltage range.The analog input gain vaule(ING), calculated
         by(max - min) / 20, analog input offSet value(INO) calculated by(min + max) / 2.
        E.g.If new wanted input range is in[0V, 5V], which means analog input gain is 0.25, analog input offSet value is
         2.5.  (the new Voltage Sampled is function of Vold, ING and INO  Vnew = ING * Vold + 1.5(1 - ING) - 0.15*INO,
         where Vout is default range's output.)
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            aiOffset: offset value of analog input: PDX1/PDX1A/PDX1AV/PDX1D/PDX1DV:[-10,10]mm; PDX2:[-2.5,2.5]mm;
            PDX3[-25,25]mm; PDX4:[-6,6]mm; PDXZ1:[-2.25,2.25]mm; PDXR:[-999.9,999.9]°; PDXG1:[-8,8]°.
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            aiO = c_double(aiOffset)
            ret = pdxc.pdxcLib.Set_AnalogInputOffSet(self.hdl, secondary, aiO)
        return ret

    def SetAnalogOutGain(self, secondary, aoGain):
        """Change gain Value of analog output, default output range is[-10V, 10V].If change value of Gain&Offset, we
        will get new output range.The analog out gain value(OUG), The analog out offset value(OUO).E.g.If new wanted
        output range is in[0V, 5V], which means OUG = 0.25, OUO = 2.5. (the new voltage output for DAC is function of
        position, which equals Vdac_new = (Vdac_old - 1.5)*OUG + OUO / 6.8 + 1.5, where Vdac_old = (pos / 100000 + 10)
        / 20 * 3).
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            aoGain: gain Value of analog output, the range is [0.1,1]V
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            aoG = c_double(aoGain)
            ret = pdxc.pdxcLib.Set_AnalogOutGain(self.hdl, secondary, aoG)
        return ret

    def SetAnalogOutOffSet(self, secondary, aoOffset):
        """Change offset Value of analog output:[-10,10].If change value of Gain&Offset, we
        will get new output range.The analog out gain value(OUG),
        The analog out offset value(OUO).E.g.If new wanted output range is in[0V, 5V], which means OUG = 0.25, OUO = 2.5
        . (the new voltage output for DAC is function of position, which equals Vdac_new =
        (Vdac_old - 1.5)*OUG + OUO / 6.8 + 1.5, where Vdac_old = (pos / 100000 + 10) / 20 * 3).
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            aoOffset: offset Value of analog output:PDX1/PDX2//PDX3/PDX4/PDX1A/PDX1AV/PDX1D/PDX1DV:[-10,10]mm;
            PDXZ1[-2.25,2.25]mm; PDXR:[-999.9,999.9]°; PDXG1:[-8,8]°.
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            aoO = c_double(aoOffset)
            ret = pdxc.pdxcLib.Set_AnalogOutOffSet(self.hdl, secondary, aoO)
        return ret

    def SetAllCustomerData(self, secondary, saveState):
        """Data contains SMC data and non - SMC data, the former one contains velocity and step size for each channel,
        and the later one contains status(reserved), speed for closedloop, Velocity Level for openloop, position and
        step size, daisy - chain number, input trigger value abnormal detection value input / output gain and offset(4
        in all), and step distance.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            saveState: set to save or erase(1:save data,0:erase data.)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            saveS = c_int(saveState)
            ret = pdxc.pdxcLib.Set_AllCustomerData(self.hdl, secondary, saveS)
        return ret

    def SetOpenLoopMoveForward(self, secondary, pulses, channel):
        """Set Open Loop Move Forward
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            pulses: pulses of move channel:SMC[1,65535]; PD2/PD3[1,400000]
            channel: Move fordward channel (0 : channel 1, 1 : channel 2, others :both channels)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            pul = c_int(pulses)
            chan = c_int(channel)
            ret = pdxc.pdxcLib.Set_OpenLoopMoveForward(self.hdl, secondary, pul, chan)
        return ret

    def SetOpenLoopMoveBack(self, secondary, pulses, channel):
        """Set Open Loop Move Forward
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            pulses: pulses of move channel:SMC[1,65535]; PD2/PD3[1,400000]
            channel: Move fordward channel (0 : channel 1, 1 : channel 2, others :both channels)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            pul = c_int(pulses)
            chan = c_int(channel)
            ret = pdxc.pdxcLib.Set_OpenLoopMoveBack(self.hdl, secondary, pul, chan)
        return ret

    def SetDisabled(self, secondary, disable):
        """Set controller disabled
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            disable: disable state(0:enable the device, 1:disable the device)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            dis = c_int(disable)
            ret = pdxc.pdxcLib.Set_Disabled(self.hdl, secondary, dis)
        return ret

    def SetCurrentStatusInExternalTrigger(self, secondary, triggerMode):
        """Set the current status of external trigger mode
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            triggerMode: "ML"(Manual mode), "AR/AF"(Analog - In mode with rising / falling edge), "FR/FF[value]"(Fixed
            - Step size mode), and "PR/PF[pos1],PR/PF[pos2]"(Two - Postion Switching mode).
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            trig = c_char_p(triggerMode.encode('utf-8'))
            ret = pdxc.pdxcLib.Set_CurrentStatusInExternalTrigger(self.hdl, secondary, trig)
        return ret

    def SetPositionLimit(self, secondary, minvalue, maxvalue):
        """Set the minimum and maximum values of position, the controller will not respond to the value surpass this
        range.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            minvalue: Minimum value of position, PDX1/PDX1A/PDX1AV/PDX1D/PDX1DV range[-10,max] mm; PDX2 range[-2.5,max] mm;
                PDX3 range[-25,max] mm; PDX4 range[-6,max] mm;  PDXZ1 range[-2.25,max] mm; PDXR range[-999.9,max] °;
                PDXG1 range[-8,max] °.
            maxvalue: Maximum value of position, PDX1/PDX1A/PDX1AV/PDX1D/PDX1DV range[min,10] mm; PDX2 range[min,2.5] mm;
                PDX3 range[min,25] mm; PDX4 range[min,6] mm;  PDXZ1 range[min,2.25] mm; PDXR range[min,999.9] °; PDXG1 range[min,8] °.
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            minva = c_double(minvalue)
            maxva = c_double(maxvalue)
            ret = pdxc.pdxcLib.Set_PositionLimit(self.hdl, secondary, minva, maxva)
        return ret

    def SetJoystickConfig(self, secondary, value, value2):
        """Set the joystick config for device.
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            value: 0:No device; 1:Single-Mode or Main; 2 -12 : Secondary1-Secondary11
            value2: The number of knob on joystick[from 0 to n(0:no knob; 1:fixed to 1:Single-Mode or Main)]
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            val = c_int(value)
            val2 = c_int(value2)
            ret = pdxc.pdxcLib.Set_JoystickConfig(self.hdl, secondary, val, val2)
        return ret

    def SetStepPulseAndResponse(self, secondary, value):
        """Set step position
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            value: relative distance to be moved:
                    PDX1/PDX1A/PDX1AV:[-10,-0.00001],[0.00001,10]mm;
                    PDX1:[-10,-0.00001],[0.00001,10]mm;
                    PDX1A/PDX1AV:[-10,-0.0001],[0.0001,10]mm;
                    PDX1D/PDX1DV:[-10,-0.0001],[0.0001,10]mm;
                    PDX2:[-2.5,-0.0003],[0.0003,2.5]mm;
                    PDX3:[-25,-0.0003],[0.0003,25]mm;
                    PDX4:[-6,-0.0003],[0.0003,6]mm;
                    PDXZ1:[-2.25,-0.0001],[0.0001,2.25]mm;
                    PDXR:[-180,-0.00005],[0.00005,180]°.
                    PDXR:[-180,-0.00005],[0.00005,180]°;
                    PDXG1:[-8,-0.0003],[0.0003,8]°.
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            val = c_double(value)
            ret = pdxc.pdxcLib.Set_StepPulseAndResponse(self.hdl, secondary, val)
        return ret

    def SetInitPosition(self, secondary, value):
        """Set init position state
        Args:
            secondary: index in daisy chain (0:Single Mode or Main, 1 -11 : Secondary1 - Secondary11)
            value: init position state(0:stages will keep motionless when controller powered on, 1:stages will return
            to the last saved position when powered on)
        Returns:
            0: Success; negative number: failed.
        """
        ret = -1
        if self.hdl >= 0:
            val = c_int(value)
            ret = pdxc.pdxcLib.Set_InitPosition(self.hdl, secondary, val)
        return ret
