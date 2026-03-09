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
!define APP_VERSION   "3.0.0-beta.21"
!define APP_EXE       "NX-Librarian.exe"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "NX-Librarian-Setup.exe"
BrandingText "${APP_NAME} ${APP_VERSION}"
SetCompressor /SOLID lzma

; Portable-only: installs to user-writable AppData — no admin rights needed.
RequestExecutionLevel user
InstallDir "$LOCALAPPDATA\NX-Librarian"

; ---------------------------------------------------------------------------
; MUI
; ---------------------------------------------------------------------------
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "..\icon.ico"
!define MUI_UNICON "..\icon.ico"

; Finish page — offer to launch the app
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"

; Pages
Page custom ShortcutPageCreate ShortcutPageLeave
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

; ---------------------------------------------------------------------------
; Desktop shortcut option
; ---------------------------------------------------------------------------
Var Dialog
Var CheckDesktop
Var DesktopShortcut

Function ShortcutPageCreate
    nsDialogs::Create 1018
    Pop $Dialog
    ${If} $Dialog == error
        Abort
    ${EndIf}

    ${NSD_CreateLabel} 0 0 100% 20u \
        "Choose install location on the next page (default: AppData\Local\NX-Librarian)."

    ${NSD_CreateCheckbox} 10u 30u 90% 14u "Create Desktop shortcut"
    Pop $CheckDesktop
    ${NSD_SetState} $CheckDesktop ${BST_CHECKED}

    nsDialogs::Show
FunctionEnd

Function ShortcutPageLeave
    ${NSD_GetState} $CheckDesktop $DesktopShortcut
FunctionEnd

; ---------------------------------------------------------------------------
; Installer
; ---------------------------------------------------------------------------
Section "Main Application" SecMain
    SectionIn RO

    SetOutPath $INSTDIR
    File "..\dist\${APP_EXE}"

    ; Auto-update (silent): just replace the binary and exit.
    ; The updater batch script relaunches the app after we exit.
    ${If} ${Silent}
        Return
    ${EndIf}

    ; Desktop shortcut (optional)
    ${If} $DesktopShortcut == ${BST_CHECKED}
        CreateShortcut "$DESKTOP\NX-Librarian.lnk" "$INSTDIR\${APP_EXE}"
    ${EndIf}
SectionEnd

