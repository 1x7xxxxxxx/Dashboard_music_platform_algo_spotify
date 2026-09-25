# Sourced by secret_prompt.sh and rotate_secret.sh — defines `dialog VAR [STEP]`, which
# prints the value typed in a masked Windows dialog on stdout (captured, never shown).
# SECRET_PROMPT_CMD overrides the dialog (tests).
#
# The dialog NAMES the account and the console the value comes from (2026-09-25: two
# windows in a row titled only with a variable name left the owner guessing which Gmail
# account each one wanted). A variable absent from secret_hint falls back to
# SECRET_HINT_<VAR> from the environment, then to its bare name.

secret_hint() {  # $1 = VAR ; prints "account | where to get the value"
    case "$1" in
        GMAIL_APP_PASSWORD_NINEKA)   echo "Compte Gmail : nineka50130@gmail.com|Mot de passe d'application — myaccount.google.com/apppasswords, connecté à CE compte" ;;
        GMAIL_APP_PASSWORD_127BPMIN) echo "Compte Gmail : 127bpmin@gmail.com|Mot de passe d'application — myaccount.google.com/apppasswords, connecté à CE compte" ;;
        GMAIL_APP_PASSWORD_1X7)      echo "Compte Gmail : 1x7xxxxxxx@gmail.com|Mot de passe d'application — myaccount.google.com/apppasswords, connecté à CE compte" ;;
        SPOTIFY_CLIENT_SECRET)       echo "Spotify — app centrale streaMLytics|developer.spotify.com/dashboard → ton app → Settings → Client secret (après « Rotate »)" ;;
        YOUTUBE_API_KEY)             echo "YouTube — clé API Google Cloud|console.cloud.google.com/apis/credentials → ta clé → « Regenerate key »" ;;
        META_APP_SECRET)             echo "Meta — app développeur|developers.facebook.com/apps → Paramètres → Général → Clé secrète (après « Réinitialiser »)" ;;
        SOUNDCLOUD_CLIENT_SECRET)    echo "SoundCloud — app développeur|soundcloud.com/you/apps → ton app → Client secret" ;;
        *) local env_hint="SECRET_HINT_$1"
           echo "${!env_hint:-$1}|" ;;
    esac
}

dialog() {  # $1 = VAR, $2 = "i/n" (optional) ; prints the typed value on stdout, nothing else
    if [ -n "${SECRET_PROMPT_CMD-}" ]; then sh -c "$SECRET_PROMPT_CMD"; return; fi
    local h; h="$(secret_hint "$1")"
    # WSLENV is what carries a variable across to a Windows process; without it the four
    # labels reach PowerShell EMPTY — the first version showed a blank window (2026-09-25).
    VAR_LABEL="$1" VAR_STEP="${2-}" VAR_WHO="${h%%|*}" VAR_WHERE="${h#*|}" \
    WSLENV="VAR_LABEL:VAR_STEP:VAR_WHO:VAR_WHERE${WSLENV:+:$WSLENV}" \
    powershell.exe -NoProfile -STA -Command '
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
$step = ""; if ($env:VAR_STEP) { $step = " (" + $env:VAR_STEP + ")" }
$f = New-Object Windows.Forms.Form
$f.Text = "Secret" + $step + " : " + $env:VAR_WHO; $f.Width = 560; $f.Height = 230
$f.TopMost = $true; $f.StartPosition = "CenterScreen"
$who = New-Object Windows.Forms.Label; $who.Text = $env:VAR_WHO
$who.Font = New-Object Drawing.Font("Segoe UI", 12, [Drawing.FontStyle]::Bold)
$who.Left = 12; $who.Top = 10; $who.Width = 520; $who.Height = 26
$where = New-Object Windows.Forms.Label; $where.Text = $env:VAR_WHERE
$where.Left = 12; $where.Top = 40; $where.Width = 520; $where.Height = 34
$var = New-Object Windows.Forms.Label; $var.Text = "Ecrit dans : " + $env:VAR_LABEL
$var.ForeColor = [Drawing.Color]::Gray; $var.Left = 12; $var.Top = 76; $var.Width = 520
$t = New-Object Windows.Forms.TextBox; $t.UseSystemPasswordChar = $true
$t.Left = 12; $t.Top = 104; $t.Width = 520
$b = New-Object Windows.Forms.Button; $b.Text = "OK"; $b.Left = 452; $b.Top = 140
$b.DialogResult = [Windows.Forms.DialogResult]::OK
$f.AcceptButton = $b; $f.Controls.AddRange(@($who, $where, $var, $t, $b))
$f.Add_Shown({ $f.Activate(); $t.Focus() })
if ($f.ShowDialog() -eq "OK") { [Console]::Out.Write($t.Text) }
' | tr -d '\r'
}
