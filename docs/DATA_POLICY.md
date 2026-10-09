# Inputs and publication boundaries

This GitHub package contains authored documents, source code, configuration, schemas and synthetic fixtures. Vendor earnings PDFs, workbooks/research exports, private portfolio/account data, credentials, broker responses, runtime databases and historical market datasets are not included.

Store private/licensed inputs in an access-controlled location outside the tracked repository. Preserve filenames or safe aliases, source/session dates, actual receipt times, secure hashes and original row identities for reproducible authorised evaluation. Do not publish raw vendor text or prices without confirmed redistribution rights.

The retained weekly parser expects its original local data layout. Supplying those inputs privately is a separate operator step. Current exported options records are not a complete historical short-DTE archive; absence is not zero flow.

Never commit API tokens, private keys, authentication cookies, real position/account identifiers or logs containing them. Empty `.env.example` is documentation for future inputs, not an implemented live producer. Generated results and state are ignored by Git.

The PDF and prompt files contain the user's authored strategy and generic protected ticker names, with no account credentials or actual position IDs. Copier notes remain drafts until explicitly authorised for publication.
