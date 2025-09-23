# Release process
1) Bump submodule(s) to new commits.
2) Run `make e2e` and ensure green.
3) Run `make lock` to pin SHAs in MANIFEST.yml.
4) Tag repo with arch-YYYY.MM.DD-N.
