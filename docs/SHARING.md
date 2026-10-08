# Sharing with eToro staff

Share the [repository](https://github.com/Flateninvest/Active-Trading-OverNight) or the [reviewer guide](https://github.com/Flateninvest/Active-Trading-OverNight/blob/main/docs/README.md). The stable version is on `main`.

## Reading and editing

- The repository is **public**. Anyone, including eToro staff, can read and download the published files without a GitHub account or invitation. Public means visible to everyone, not only people receiving the link.
- Public visibility does not grant permission to push commits or merge changes into this repository. Readers can edit their own fork and propose a pull request; that does not edit the original project.
- Do not invite staff as collaborators just to read. Collaborators on a personal repository receive write access. Owner-authorized tools may still act on the owner's behalf.

The 8 October 2026 access check verified anonymous reading and found no outside collaborators, pending invitations or deploy keys. The repository owner, `Flateninvest`, retains human write and administration access. This is a dated check; audit access again when adding collaborators or integrations.

## Protection for the shared version

`main` requires a pull request, a passing `synthetic-checks` check on an up-to-date branch and resolved review conversations. Force pushes and branch deletion are blocked. These rules also apply to the owner.

There is no mandatory external approving review because the owner is the only human writer and cannot approve their own pull request. The owner reviews and merges changes; readers have no merge permission. CODEOWNERS records responsibility without granting access.

Follow [the contribution guide](../CONTRIBUTING.md) for updates. These repository settings govern code publication, not broker orders or trading approval.

## Publication boundary

Publish code, authored project documents, safe configuration and synthetic examples. Keep vendor workbooks, portfolio/account records, credentials and runtime state private under [the data policy](DATA_POLICY.md). Reading access permits copies; it cannot prevent readers saving files.

If access should later be restricted to named staff, use a private organization repository with the Read role. A private repository owned by a personal account does not offer read-only collaborator access. See GitHub's [personal repository permissions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository) and [organization repository roles](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization).
