Structured raw archive for KIPRIS rejection dataset.

Layout:
- <application_number>/target/target_patent_<application_number>.txt
- <application_number>/rejection_notice/rejection_notice_<application_number>.txt
- <application_number>/cited/*.txt
- <application_number>/README.txt

Notes:
- Resolved cited patents include extracted original text.
- Unresolved cited patents are stored as metadata placeholder files with the cited identifier and notice evidence.
