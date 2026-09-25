# Start Odoo 19 for ClinicOS development.
# Usage:
#   .\run.ps1                              # run server on db "clinicos"
#   .\run.ps1 -u my_module                 # upgrade a module, then keep serving
#   .\run.ps1 -i my_module                 # install a module
#   .\run.ps1 -d other_db                  # use a different database
# Extra args are passed straight to odoo-bin.
param(
    [string]$d = "clinicos",
    [Parameter(ValueFromRemainingArguments = $true)] $rest
)
$root = $PSScriptRoot
& "$root\.venv\Scripts\python.exe" "$root\odoo\odoo-bin" -c "$root\odoo.conf" -d $d --dev=xml,reload @rest
