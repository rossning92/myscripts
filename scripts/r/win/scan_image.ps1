function ScanToImage([string]$file) {
    $ErrorActionPreference = "Stop"
    $deviceManager = new-object -ComObject WIA.DeviceManager
    $ScannerDeviceType = 1
    foreach ($deviceInfo in $deviceManager.DeviceInfos) {
        if ($deviceInfo.Type -eq $ScannerDeviceType) {
            $device = $deviceInfo.Connect()
        }
    }

    $wiaFormatJPEG = "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}"
    foreach ($device in $device.Items) {
        $device.Properties("6147").Value = 300
        $device.Properties("6148").Value = 300
        $image = $device.Transfer($wiaFormatJPEG)
    }

    if ($image.FormatID -ne $wiaFormatJPEG) {
        $imageProcess = new-object -ComObject WIA.ImageProcess

        $imageProcess.Filters.Add($imageProcess.FilterInfos.Item("Convert").FilterID)
        $imageProcess.Filters.Item(1).Properties.Item("FormatID").Value = $wiaFormatJPEG
        $image = $imageProcess.Apply($image)
    }

    $image.SaveFile("$file")
}

if ($args.count -eq 1) {
    $file = $args[0]
}
else {
    $dateStr = Get-Date -format "yyyyMMdd_HHmmss"
    $file = [Environment]::GetFolderPath("Desktop") + "\$dateStr.jpg"
}
Write-Output "Scan and save to: $file"
ScanToImage("$file")
