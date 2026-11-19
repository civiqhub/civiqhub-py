// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

// The version selector of the sidebar.
//
// The published site holds one folder per version, and a file versions.json next to
// these folders. This script reads that file and fills the selector. On a choice it
// opens the same page in the chosen version when the page exists there, and the home
// page of that version otherwise.
//
// Outside the published site (a local build, a build kept by the CI) there is no
// versions.json: the selector stays hidden.
(async () => {
  const box = document.querySelector(".version-switcher");
  if (!box) return;
  const select = box.querySelector("select");

  // Sphinx writes on <html> the path from this page to the root of its version.
  const contentRoot = document.documentElement.dataset.content_root || "./";
  const versionRoot = new URL(contentRoot, window.location.href);
  const siteRoot = new URL("../", versionRoot);

  let listed;
  try {
    const response = await fetch(new URL("versions.json", siteRoot), { cache: "no-cache" });
    if (!response.ok) return;
    listed = (await response.json()).versions;
  } catch {
    return;
  }
  if (!Array.isArray(listed)) return;

  let current = false;
  for (const version of listed) {
    const root = new URL(version.path, siteRoot);
    const option = new Option(version.label, root.href);
    option.selected = root.pathname === versionRoot.pathname;
    current = current || option.selected;
    select.add(option);
  }
  // This page belongs to no listed version: nothing to switch from.
  if (!current) return;

  const page = window.location.pathname.slice(versionRoot.pathname.length);
  select.addEventListener("change", async () => {
    const home = select.value;
    let target = home;
    try {
      const response = await fetch(home + page, { method: "HEAD" });
      if (response.ok) target = home + page + window.location.hash;
    } catch {
      // The home page of the version is the fallback.
    }
    window.location.assign(target);
  });
  box.hidden = false;
})();
