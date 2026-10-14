using System;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace SleepStageR17
{
    public static class NativeMethods
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct PROCESS_BASIC_INFORMATION
        {
            public IntPtr Reserved1;
            public IntPtr PebBaseAddress;
            public IntPtr Reserved2_0;
            public IntPtr Reserved2_1;
            public IntPtr UniqueProcessId;
            public IntPtr InheritedFromUniqueProcessId;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct SYSTEM_POWER_STATUS
        {
            public byte ACLineStatus;
            public byte BatteryFlag;
            public byte BatteryLifePercent;
            public byte SystemStatusFlag;
            public UInt32 BatteryLifeTime;
            public UInt32 BatteryFullLifeTime;
        }

        [DllImport("ntdll.dll")]
        private static extern int NtQueryInformationProcess(
            IntPtr processHandle,
            int processInformationClass,
            ref PROCESS_BASIC_INFORMATION processInformation,
            int processInformationLength,
            out int returnLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GetSystemPowerStatus(out SYSTEM_POWER_STATUS status);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool GetDiskFreeSpaceEx(
            string directoryName,
            out UInt64 freeBytesAvailable,
            out UInt64 totalNumberOfBytes,
            out UInt64 totalNumberOfFreeBytes);

        public static int GetCurrentParentProcessId()
        {
            PROCESS_BASIC_INFORMATION info = new PROCESS_BASIC_INFORMATION();
            int returned;
            using (Process process = Process.GetCurrentProcess())
            {
                int status = NtQueryInformationProcess(
                    process.Handle,
                    0,
                    ref info,
                    Marshal.SizeOf(typeof(PROCESS_BASIC_INFORMATION)),
                    out returned);
                if (status != 0)
                {
                    throw new InvalidOperationException(
                        "NtQueryInformationProcess failed with NTSTATUS 0x" + status.ToString("X8"));
                }
            }
            return checked((int)info.InheritedFromUniqueProcessId.ToInt64());
        }

        public static SYSTEM_POWER_STATUS GetPowerStatus()
        {
            SYSTEM_POWER_STATUS status;
            if (!GetSystemPowerStatus(out status))
            {
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            }
            return status;
        }

        public static UInt64 GetFreeBytesAvailable(string rootPath)
        {
            UInt64 freeBytesAvailable;
            UInt64 totalNumberOfBytes;
            UInt64 totalNumberOfFreeBytes;
            if (!GetDiskFreeSpaceEx(
                    rootPath,
                    out freeBytesAvailable,
                    out totalNumberOfBytes,
                    out totalNumberOfFreeBytes))
            {
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            }
            return freeBytesAvailable;
        }
    }
}


