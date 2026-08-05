Add-Type -MemberDefinition '[DllImport("ntdll.dll")] public static extern int NtSetSystemInformation(int InfoClass, ref uint Info, int Length);' -Name NtDll -Namespace Win32
$cmd = [uint32]4
[Win32.NtDll]::NtSetSystemInformation(80, [ref]$cmd, 4)
