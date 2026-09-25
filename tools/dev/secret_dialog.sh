# Sourced by secret_prompt.sh and rotate_secret.sh — defines dialog VAR, which prints
# the value typed in a masked Windows dialog on stdout (captured, never shown).
# SECRET_PROMPT_CMD overrides it (tests).
dialog() {  # $1 = VAR ; prints the typed value on stdout, nothing else
    if [ -n "${SECRET_PROMPT_CMD-}" ]; then sh -c "$SECRET_PROMPT_CMD"; return; fi
    VAR_LABEL="$1" powershell.exe -NoProfile -STA -Command '
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object Windows.Forms.Form
$f.Text = "Secret : " + $env:VAR_LABEL; $f.Width = 460; $f.Height = 160
$f.TopMost = $true; $f.StartPosition = "CenterScreen"
$l = New-Object Windows.Forms.Label; $l.Text = "Colle la valeur de " + $env:VAR_LABEL + " puis Entree"
$l.Left = 12; $l.Top = 12; $l.Width = 420
$t = New-Object Windows.Forms.TextBox; $t.UseSystemPasswordChar = $true
$t.Left = 12; $t.Top = 40; $t.Width = 420
$b = New-Object Windows.Forms.Button; $b.Text = "OK"; $b.Left = 352; $b.Top = 72
$b.DialogResult = [Windows.Forms.DialogResult]::OK
$f.AcceptButton = $b; $f.Controls.AddRange(@($l, $t, $b))
$f.Add_Shown({ $f.Activate(); $t.Focus() })
if ($f.ShowDialog() -eq "OK") { [Console]::Out.Write($t.Text) }
' | tr -d '\r'
}
