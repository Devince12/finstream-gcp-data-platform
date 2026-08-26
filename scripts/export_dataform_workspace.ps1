$ProjectId = "fintech-data-platform-dev"
$Location = "europe-west1"
$Repository = "finstream-dataform"
$Workspace = "dev"

$OutputDir = "C:\Users\LENOVO\gcp-fintech-pipeline\finstream-gcp\dataform"

# ============================================================
# Prepare local destination
# ============================================================

New-Item `
    -ItemType Directory `
    -Force `
    -Path $OutputDir `
    | Out-Null


# ============================================================
# Authentication
# ============================================================

$Token = gcloud auth print-access-token

if ([string]::IsNullOrWhiteSpace($Token)) {
    throw "Unable to retrieve Google Cloud access token."
}


# ============================================================
# Dataform workspace configuration
# ============================================================

$WorkspaceName = (
    "projects/$ProjectId/" +
    "locations/$Location/" +
    "repositories/$Repository/" +
    "workspaces/$Workspace"
)

$BaseUrl = "https://dataform.googleapis.com/v1/$WorkspaceName"

$Headers = @{
    Authorization = "Bearer $Token"
}


# ============================================================
# Get directory contents
# ============================================================

function Get-DirectoryContents {

    param (
        [string]$Path = ""
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {

        $Url = (
            "$BaseUrl" +
            ":queryDirectoryContents" +
            "?pageSize=1000"
        )
    }
    else {

        $EncodedPath = [uri]::EscapeDataString(
            $Path
        )

        $Url = (
            "$BaseUrl" +
            ":queryDirectoryContents" +
            "?path=$EncodedPath" +
            "&pageSize=1000"
        )
    }

    try {

        return Invoke-RestMethod `
            -Method Get `
            -Uri $Url `
            -Headers $Headers
    }
    catch {

        throw (
            "Unable to list Dataform directory '$Path'. " +
            $_.Exception.Message
        )
    }
}


# ============================================================
# Read a Dataform file
# ============================================================

function Read-DataformFile {

    param (
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $EncodedPath = [uri]::EscapeDataString(
        $Path
    )

    $Url = (
        "$BaseUrl" +
        ":readFile" +
        "?path=$EncodedPath"
    )

    try {

        $Response = Invoke-RestMethod `
            -Method Get `
            -Uri $Url `
            -Headers $Headers

    }
    catch {

        throw (
            "Unable to read Dataform file '$Path'. " +
            $_.Exception.Message
        )
    }

    if ($null -eq $Response.fileContents) {

        throw (
            "Dataform returned no fileContents " +
            "for '$Path'."
        )
    }

    try {

        $Bytes = [System.Convert]::FromBase64String(
            $Response.fileContents
        )

        return [System.Text.Encoding]::UTF8.GetString(
            $Bytes
        )

    }
    catch {

        throw (
            "Unable to decode Dataform file '$Path'. " +
            $_.Exception.Message
        )
    }
}


# ============================================================
# Export directory recursively
# ============================================================

function Export-Directory {

    param (
        [string]$RemotePath = ""
    )

    $Contents = Get-DirectoryContents `
        -Path $RemotePath


    foreach ($Entry in $Contents.directoryEntries) {

        # ====================================================
        # Directory
        # ====================================================

        if ($null -ne $Entry.directory) {

            $DirectoryPath = $Entry.directory

            # Do not export generated dependencies.
            if (
                $DirectoryPath -eq "node_modules" -or
                $DirectoryPath.StartsWith("node_modules/")
            ) {

                Write-Host (
                    "Skipping directory: " +
                    $DirectoryPath
                )

                continue
            }

            Write-Host (
                "Directory: " +
                $DirectoryPath
            )

            $LocalDirectory = Join-Path `
                $OutputDir `
                $DirectoryPath

            New-Item `
                -ItemType Directory `
                -Force `
                -Path $LocalDirectory `
                | Out-Null

            Export-Directory `
                -RemotePath $DirectoryPath
        }


        # ====================================================
        # File
        # ====================================================

        elseif ($null -ne $Entry.file) {

            $FilePath = $Entry.file

            Write-Host (
                "Exporting: " +
                $FilePath
            )

            $LocalFile = Join-Path `
                $OutputDir `
                $FilePath

            $ParentDirectory = Split-Path `
                $LocalFile `
                -Parent

            if (
                -not [string]::IsNullOrWhiteSpace(
                    $ParentDirectory
                )
            ) {

                New-Item `
                    -ItemType Directory `
                    -Force `
                    -Path $ParentDirectory `
                    | Out-Null
            }

            $Content = Read-DataformFile `
                -Path $FilePath

            Set-Content `
                -Path $LocalFile `
                -Value $Content `
                -Encoding UTF8
        }
    }
}


# ============================================================
# Main execution
# ============================================================

Write-Host ""
Write-Host "============================================"
Write-Host " FinStream Dataform Workspace Export"
Write-Host "============================================"
Write-Host ""
Write-Host "Workspace:"
Write-Host $WorkspaceName
Write-Host ""
Write-Host "Destination:"
Write-Host $OutputDir
Write-Host ""


try {

    Export-Directory

    Write-Host ""
    Write-Host "============================================"
    Write-Host " Dataform export completed successfully"
    Write-Host "============================================"
    Write-Host ""

}
catch {

    Write-Host ""
    Write-Error $_
    exit 1
}