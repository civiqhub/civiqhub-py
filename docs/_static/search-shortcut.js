// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.

// Ctrl K and Cmd K focus the sidebar search field.
(() => {
  const inputSelector = ".sidebar-search";

  function focusSearch() {
    const input = document.querySelector(inputSelector);
    if (!(input instanceof HTMLInputElement)) {
      return;
    }
    const nav = document.getElementById("__navigation");
    if (nav instanceof HTMLInputElement && window.matchMedia("(max-width: 67em)").matches) {
      nav.checked = true;
    }
    input.focus();
    input.select();
  }

  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented) {
      return;
    }
    if (event.key.toLowerCase() !== "k" || !(event.ctrlKey || event.metaKey) || event.altKey) {
      return;
    }
    const target = event.target;
    if (target instanceof HTMLElement) {
      const tag = target.tagName;
      const inField = tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable;
      if (inField) {
        return;
      }
    }
    event.preventDefault();
    focusSearch();
  });
})();
