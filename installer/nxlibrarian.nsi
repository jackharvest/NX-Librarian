; installer/nxlibrarian.nsi - NSIS installer for NX-Librarian (Windows)
;
; Build:
;   makensis installer\nxlibrarian.nsi
;
; Produces:
;   installer\NX-Librarian-Setup.exe
;
; Requires: NSIS 3.x (https://nsis.sourceforge.io)

Unicode True

!define APP_NAME      "NX-Librarian"
!define APP_VERSION   "3.0.0-beta.9"
!define APP_EXE       "NX-Librarian.exe"
!define REGKEY        "Software\Microsoft\Windows\CurrentVersion\Uninstall\NX-Librarian"
!define UNINSTALLER   "Uninstall.exe"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "NX-Librarian-Setup.exe"
BrandingText "${APP_NAME} ${APP_VERSION}"
SetCompressor /SOLID lzma

; Allow install without UAC for portable mode;
; the user page will offer to escalate for Program Files install.
RequestExecutionLevel user

; ---------------------------------------------------------------------------
; MUI
; ---------------------------------------------------------------------------
!include "MUI2.nsh"
!include "LogicLib.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "..\icon.ico"
!define MUI_UNICON "..\icon.ico"

; Variables
Var InstallMode   ; "portable" or "install"
Var DesktopShortcut

; Pages
Page custom InstallModePageCreate InstallModePageLeave
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ---------------------------------------------------------------------------
; Install mode custom page
; ---------------------------------------------------------------------------
!include "nsDialogs.nsh"
Var Dialog
Var RadioPortable
Var RadioInstall
Var CheckDesktop

Function InstallModePageCreate
    nsDialogs::Create 1018
    Pop $Dialog
    ${If} $Dialog == error
        Abort
    ${EndIf}

    ${NSD_CreateLabel} 0 0 100% 30u \
        "How would you like to install ${APP_NAME}?"

    ${NSD_CreateRadioButton} 10u 35u 90% 14u \
        "Portable - copy to a folder of your choice (no registry entries, no Start Menu)"
    Pop $RadioPortable
    ${NSD_SetState} $RadioPortable ${BST_CHECKED}

    ${NSD_CreateRadioButton} 10u 55u 90% 14u \
        "Install to Program Files (creates Start Menu shortcut, optional Desktop shortcut)"
    Pop $RadioInstall

    ${NSD_CreateCheckbox} 20u 75u 90% 14u \
        "Create Desktop shortcut"
    Pop $CheckDesktop
    ${NSD_SetState} $CheckDesktop ${BST_CHECKED}

    nsDialogs::Show
FunctionEnd

Function InstallModePageLeave
    ${NSD_GetState} $RadioPortable $0
    ${If} $0 == ${BST_CHECKED}
        StrCpy $InstallMode "portable"
        ; Portable: suggest a simple writable folder
        StrCpy $INSTDIR "$LOCALAPPDATA\NX-Librarian"
    ${Else}
        StrCpy $InstallMode "install"
        StrCpy $INSTDIR "$PROGRAMFILES64\NX-Librarian"
    ${EndIf}

    ${NSD_GetState} $CheckDesktop $DesktopShortcut
FunctionEnd

; ---------------------------------------------------------------------------
; Installer
; ---------------------------------------------------------------------------
Section "Main Application" SecMain
    SectionIn RO

    SetOutPath $INSTDIR
    File "..\dist\${APP_EXE}"

    ${If} $InstallMode == "install"
        ; Write uninstaller
        WriteUninstaller "$INSTDIR\${UNINSTALLER}"

        ; Start Menu
        CreateDirectory "$SMPROGRAMS\NX-Librarian"
        CreateShortcut  "$SMPROGRAMS\NX-Librarian\NX-Librarian.lnk" \
                        "$INSTDIR\${APP_EXE}"
        CreateShortcut  "$SMPROGRAMS\NX-Librarian\Uninstall.lnk" \
                        "$INSTDIR\${UNINSTALLER}"

        ; Desktop shortcut (optional)
        ${If} $DesktopShortcut == ${BST_CHECKED}
            CreateShortcut "$DESKTOP\NX-Librarian.lnk" "$INSTDIR\${APP_EXE}"
        ${EndIf}

        ; Registry (HKCU - no UAC required)
        WriteRegStr   HKCU "${REGKEY}" "DisplayName"     "${APP_NAME}"
        WriteRegStr   HKCU "${REGKEY}" "DisplayVersion"  "${APP_VERSION}"
        WriteRegStr   HKCU "${REGKEY}" "Publisher"       "jackharvest"
        WriteRegStr   HKCU "${REGKEY}" "UninstallString" '"$INSTDIR\${UNINSTALLER}"'
        WriteRegStr   HKCU "${REGKEY}" "InstallLocation" "$INSTDIR"
        WriteRegDWORD HKCU "${REGKEY}" "NoModify"        1
        WriteRegDWORD HKCU "${REGKEY}" "NoRepair"        1
    ${Else}
        ; Portable: just launch and exit
        Exec '"$INSTDIR\${APP_EXE}"'
    ${EndIf}
SectionEnd

; ---------------------------------------------------------------------------
; Uninstaller
; ---------------------------------------------------------------------------
Section "Uninstall"
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\${UNINSTALLER}"
    RMDir  "$INSTDIR"

    Delete "$SMPROGRAMS\NX-Librarian\NX-Librarian.lnk"
    Delete "$SMPROGRAMS\NX-Librarian\Uninstall.lnk"
    RMDir  "$SMPROGRAMS\NX-Librarian"

    Delete "$DESKTOP\NX-Librarian.lnk"

    DeleteRegKey HKCU "${REGKEY}"
SectionEnd
