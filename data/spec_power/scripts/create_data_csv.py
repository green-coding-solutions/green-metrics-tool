import csv, re, os

header = ['100.ActualLoad', '100.ssj_ops', '100.AvgPower', '100.PerfPowerRatio',
'90.ActualLoad', '90.ssj_ops', '90.AvgPower', '90.PerfPowerRatio',
'80.ActualLoad', '80.ssj_ops', '80.AvgPower', '80.PerfPowerRatio',
'70.ActualLoad', '70.ssj_ops', '70.AvgPower', '70.PerfPowerRatio',
'60.ActualLoad', '60.ssj_ops', '60.AvgPower', '60.PerfPowerRatio',
'50.ActualLoad', '50.ssj_ops', '50.AvgPower', '50.PerfPowerRatio',
'40.ActualLoad', '40.ssj_ops', '40.AvgPower', '40.PerfPowerRatio',
'30.ActualLoad', '30.ssj_ops', '30.AvgPower', '30.PerfPowerRatio',
'20.ActualLoad', '20.ssj_ops', '20.AvgPower', '20.PerfPowerRatio',
'10.ActualLoad', '10.ssj_ops', '10.AvgPower', '10.PerfPowerRatio',
'ActiveIdle', 'HW.Vendor', 'HW.Model', 'HW.FormFactor', 'HW.CPUName', 
'HW.CPUChars', 'HW.CPUFreq', 'HW.CPUsEnabled','HW.HardwareThreads', 
'HW.CPUsOrderable', 'HW.PrimaryCache', 'HW.SecondaryCache','HW.TertiaryCache',
'HW.OtherCache', 'HW.MemAmountGB','HW.DIMMNumAndSize','HW.MemDetails', 
'HW.PSUQuantAndRating', 'HW.PSUDetails','HW.DiskDrive','HW.DiskController',
'HW.NICSNumAndType', 'HW.NICSFirm/OS/Conn','HW.NetSpeedMbit','HW.Keyboard','HW.Mouse', 
'HW.OpticalDrive', 'HW.Other', 'SW.PowerManagement', 'SW.OS', 'SW.OSVersion', 
'SW.Filesystem', 'SW.JVMVendor', 'SW.JVMVersion', 'SW.JVMCLIOpts', 
'SW.JVMAffinity', 'SW.JVMInstances', 'SW.JVMInitialHeapMB', 'SW.JVMMaxHeapMB', 
'SW.JVMAddressBits', 'SW.BootFirmwareVersion', 'SW.MgmtFirmwareVersion', 
'SW.WorkloadVersion', 'SW.DirectorLocation', 'SW.Others', 
]

rows = []
rowcount=-1

for f in os.scandir('../raw/html/'):
    if f.is_file():
        rowcount+=1
        rows.append([])
        o = open(f,'r')
        text = o.read()
        o.close()

        ## Get Power Chart
        for x in range(100, 0, -10):
            m = re.search(f'<td>{x}%</td>$'
                '\s*<td>(.*)%</td>$'
                '\s*<td>(.*)</td>$'
                '\s*<td>(.*)</td>$'
                '\s*<td>(.*)</td>$'
                , text, re.M)
            if m:
                ssj_ops_cln = re.sub(',', "", m.group(2))
                perf_pwr_ratio_cln = re.sub(',', "", m.group(4))
                rows[rowcount].extend([m.group(1), ssj_ops_cln, m.group(3), perf_pwr_ratio_cln])
                #print(f"Actual Load: {m.group(1)} --- ssj_ops: {m.group(2)} --- avg.power: {m.group(3)} --- perf.power.ratio: {m.group(4)}\n")
        
        ## Get Idle Power
        m = re.search('Active Idle.*$'
            '\s*<td>.*</td>$'
            '\s*<td>(.*)</td>$'
            , text, re.M)
        if m: rows[rowcount].append(m.group(1))

        ## Get Hardware Info
        m = re.search('Hardware Vendor:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'   # 1 
            '\s*.*Model:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'                  # 2   
            '\s*.*Form Factor:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'            # 3
            '\s*.*CPU Name:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'               # 4
            '\s*.*CPU Characteristics:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'    # 5
            '\s*.*CPU Frequency \(MHz\):</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'  # 6
            '\s*.*CPU\(s\) Enabled:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'       # 7
            '\s*.*Hardware Threads:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'       # 8
            '\s*.*CPU\(s\) Orderable:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'     # 9
            '\s*.*Primary Cache:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'          # 10
            '\s*.*Secondary Cache:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'        # 11
            '\s*.*Tertiary Cache:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'         # 12
            '\s*.*Other Cache:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'            # 13
            '\s*.*Memory Amount \(GB\):</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'   # 14 
            '\s*.*# and size of DIMM:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'     # 15
            '\s*.*Memory Details:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'         # 16
            '\s*.*Power Supply Quantity and Rating \(W\):</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$' #17
            '\s*.*Power Supply Details:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'   # 18
            '\s*.*Disk Drive:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'             # 19
            '\s*.*Disk Controller:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'        # 20
            '\s*.*# and type of Network Interface Cards \(NICs\) Installed:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$' # 21
            '\s*.*NICs Enabled in Firmware / OS / Connected:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$' # 22
            '\s*.*Network Speed \(Mbit\):</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$' # 23
            '\s*.*Keyboard:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'               # 24
            '\s*.*Mouse:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'                  # 25
            '\s*.*Monitor:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'                # 26
            '\s*.*Optical Drives:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'         # 27
            '\s*.*Other Hardware:</a></td>$\s*.*>(.*)</td>'                          # 28
            ,text , re.M)

        if m: #print(m.group(28))
            for x in range(1,29):
                rows[rowcount].append(m.group(x))

        ## Get Software Info
        m = re.search('Power Management:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'  # 1
            '\s*.*Operating System \(OS\):</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$' # 2   
            '\s*.*OS Version:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'             # 3   
            '\s*.*Filesystem:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'             # 4   
            '\s*.*JVM Vendor:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'             # 5   
            '\s*.*JVM Version:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'            # 6   
            '\s*.*JVM Command-line Options:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$' # 7   
            '\s*.*JVM Affinity:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'           # 8
            '\s*.*JVM Instances:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'          # 9
            '\s*.*JVM Initial Heap \(MB\):</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$' # 10
            '\s*.*JVM Maximum Heap \(MB\):</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$' # 11
            '\s*.*JVM Address Bits:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'       # 12
            '\s*.*Boot Firmware Version:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'  # 13
            '\s*.*Management Firmware Version:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$' # 14
            '\s*.*Workload Version:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'       # 15
            '\s*.*Director Location:</a></td>$\s*.*>(.*)</td>\s*</tr>$\s*<tr>$'      # 16
            '\s*.*Other Software:</a></td>$\s*.*>(.*)</td>'                          # 17
            ,text , re.M)

        if m: #print(m.group(17))
            for x in range(1, 18):
                rows[rowcount].append(m.group(x))


#print(rows)
with open('spec_data.csv', 'w', encoding='UTF8', newline='') as f:
    writer = csv.writer(f, delimiter='|')
    writer.writerow(header)
    writer.writerows(rows)
