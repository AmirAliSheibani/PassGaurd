(function () {
  "use strict";

  /*
   * Keep this file ES5-compatible. PassGuard's responsive layout should still
   * work on older iOS Safari/WebViews even when newer JavaScript syntax is not
   * available. Security-sensitive password generation still requires Web Crypto.
   */

  function $(selector, root) {
    return (root || document).querySelector(selector);
  }

  function $$(selector, root) {
    var nodeList = (root || document).querySelectorAll(selector);
    var items = [];
    var index;
    for (index = 0; index < nodeList.length; index += 1) items.push(nodeList[index]);
    return items;
  }

  function forEach(items, callback) {
    var index;
    for (index = 0; index < items.length; index += 1) callback(items[index], index);
  }

  function matches(element, selector) {
    var matcher;
    if (!element || element.nodeType !== 1) return false;
    matcher = element.matches || element.msMatchesSelector || element.webkitMatchesSelector;
    return matcher ? matcher.call(element, selector) : false;
  }

  function closest(element, selector) {
    if (element && element.nodeType === 3) element = element.parentNode;
    while (element && element !== document) {
      if (matches(element, selector)) return element;
      element = element.parentElement || element.parentNode;
    }
    return null;
  }

  function removeElement(element) {
    if (element && element.parentNode) element.parentNode.removeChild(element);
  }

  function dispatchBubblingEvent(element, eventName) {
    var eventObject;
    if (!element) return;
    try {
      eventObject = new Event(eventName, { bubbles: true });
    } catch (_error) {
      eventObject = document.createEvent("Event");
      eventObject.initEvent(eventName, true, false);
    }
    element.dispatchEvent(eventObject);
  }

  function setSvgUseReference(useElement, reference) {
    if (!useElement) return;
    useElement.setAttribute("href", reference);
    try {
      useElement.setAttributeNS("http://www.w3.org/1999/xlink", "xlink:href", reference);
    } catch (_error) {
      useElement.setAttribute("xlink:href", reference);
    }
  }

  function focusSafely(element) {
    if (!element || typeof element.focus !== "function") return;
    try {
      element.focus({ preventScroll: true });
    } catch (_error) {
      element.focus();
    }
  }

  function showToast(message, type) {
    var region = $("[data-toast-region]");
    var toast;
    var icon;
    var use;
    var text;
    var iconReference;
    if (!region) return;

    type = type || "success";
    toast = document.createElement("div");
    toast.className = "toast" + (type === "error" ? " is-error" : "");
    toast.setAttribute("role", type === "error" ? "alert" : "status");

    icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("class", "icon");
    icon.setAttribute("aria-hidden", "true");
    use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    iconReference = type === "error" ? "#icon-alert-triangle" : "#icon-check-circle";
    setSvgUseReference(use, iconReference);
    icon.appendChild(use);

    text = document.createElement("span");
    text.textContent = message;
    toast.appendChild(icon);
    toast.appendChild(text);
    region.appendChild(toast);

    window.setTimeout(function () {
      toast.classList.add("is-leaving");
      window.setTimeout(function () { removeElement(toast); }, 180);
    }, 2800);
  }

  function setupSidebar() {
    var sidebar = $("#appSidebar");
    var openButton = $("[data-sidebar-open]");
    var closeButtons = $$('[data-sidebar-close]');
    if (!sidebar || !openButton) return;

    function setScrimVisibility(isVisible) {
      forEach(closeButtons, function (element) {
        if (element.classList.contains("mobile-scrim")) element.hidden = !isVisible;
      });
    }

    function openSidebar() {
      var firstLink;
      sidebar.classList.add("is-open");
      document.body.classList.add("sidebar-open");
      openButton.setAttribute("aria-expanded", "true");
      setScrimVisibility(true);
      firstLink = $("a, button", sidebar);
      if (firstLink) focusSafely(firstLink);
    }

    function closeSidebar(restoreFocus) {
      sidebar.classList.remove("is-open");
      document.body.classList.remove("sidebar-open");
      openButton.setAttribute("aria-expanded", "false");
      setScrimVisibility(false);
      if (restoreFocus) focusSafely(openButton);
    }

    openButton.addEventListener("click", function () {
      if (sidebar.classList.contains("is-open")) closeSidebar(true);
      else openSidebar();
    });

    forEach(closeButtons, function (element) {
      element.addEventListener("click", function () { closeSidebar(true); });
    });

    document.addEventListener("keydown", function (event) {
      event = event || window.event;
      if ((event.key === "Escape" || event.keyCode === 27) && sidebar.classList.contains("is-open")) {
        closeSidebar(true);
      }
    });

    window.addEventListener("resize", function () {
      if (window.innerWidth > 960 && sidebar.classList.contains("is-open")) {
        closeSidebar(false);
      }
    });
  }

  function setupMessageDismissal() {
    document.addEventListener("click", function (event) {
      var button = closest(event.target, "[data-dismiss-message]");
      var alert;
      if (!button) return;
      alert = closest(button, ".alert");
      if (alert) removeElement(alert);
    });
  }

  function setupCredentialPasswordReveal() {
    document.addEventListener("click", function (event) {
      var button = closest(event.target, "[data-password-reveal]");
      var container;
      var form;
      var output;
      var csrfInput;
      var toggleButton;
      var copyButton;
      var status;
      var xhr;
      var payload;

      if (!button || button.disabled) return;
      container = closest(button, "[data-password-display]");
      if (!container) return;

      form = $("[data-password-reveal-form]", container);
      output = $("[data-password-output]", container);
      csrfInput = form ? $("input[name=csrfmiddlewaretoken]", form) : null;
      toggleButton = $("[data-password-toggle]", container);
      copyButton = $("[data-copy-target]", container);
      status = $("[data-password-reveal-status]", container);

      if (!form || !form.action || !output || !csrfInput) {
        showToast("Password reveal is not configured correctly.", "error");
        return;
      }

      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      if (status) status.textContent = "Requesting password securely…";

      xhr = new XMLHttpRequest();
      xhr.open("POST", form.action, true);
      xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8");
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      xhr.onreadystatechange = function () {
        if (xhr.readyState !== 4) return;

        button.disabled = false;
        button.removeAttribute("aria-busy");

        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            payload = JSON.parse(xhr.responseText);
          } catch (_error) {
            payload = null;
          }

          if (payload && typeof payload.password === "string") {
            output.value = payload.password;
            button.hidden = true;
            if (toggleButton) toggleButton.hidden = false;
            if (copyButton) copyButton.disabled = false;
            if (status) status.textContent = "Password loaded. Use the eye button to show or hide it.";
            showToast("Password loaded.");
            return;
          }
        }

        if (status) status.textContent = "The password could not be loaded. Sign in again if your session expired.";
        showToast("Unable to load the password. Please try again.", "error");
      };
      xhr.send("csrfmiddlewaretoken=" + encodeURIComponent(csrfInput.value));
    });

    // Clear plaintext from the live DOM when the user leaves or reloads the page.
    window.addEventListener("pagehide", function () {
      forEach($$("[data-password-output]"), function (input) {
        input.value = "";
        input.type = "password";
      });
    });
  }

  function setupPasswordVisibility() {
    document.addEventListener("click", function (event) {
      var button = closest(event.target, "[data-password-toggle]");
      var inputId;
      var input;
      var reveal;
      var label;
      var useElement;
      var iconReference;
      if (!button) return;

      inputId = button.getAttribute("data-password-toggle");
      input = document.getElementById(inputId);
      if (!input) return;

      reveal = input.type === "password";
      input.type = reveal ? "text" : "password";
      button.setAttribute("aria-pressed", reveal ? "true" : "false");
      label = button.getAttribute("aria-label") || "Show password";
      label = label.replace(/^(Show|Hide) /, "");
      button.setAttribute("aria-label", (reveal ? "Hide " : "Show ") + label);
      useElement = $("use", button);
      iconReference = reveal ? "#icon-eye-off" : "#icon-eye";
      setSvgUseReference(useElement, iconReference);
    });
  }

  /* Rejection sampling avoids modulo bias in randomly selected characters. */
  function secureIndex(maximum) {
    var limit = Math.floor(256 / maximum) * maximum;
    var byte = new Uint8Array(1);
    do {
      window.crypto.getRandomValues(byte);
    } while (byte[0] >= limit);
    return byte[0] % maximum;
  }

  function secureCharacter(alphabet) {
    return alphabet.charAt(secureIndex(alphabet.length));
  }

  function shuffleSecurely(items) {
    var index;
    var swapIndex;
    var temporary;
    for (index = items.length - 1; index > 0; index -= 1) {
      swapIndex = secureIndex(index + 1);
      temporary = items[index];
      items[index] = items[swapIndex];
      items[swapIndex] = temporary;
    }
    return items;
  }

  function generatePassword(length) {
    var upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    var lower = "abcdefghijklmnopqrstuvwxyz";
    var digits = "0123456789";
    var symbols = "!@#$%^&*_-+=.";
    var alphabet = upper + lower + digits + symbols;
    var output = [
      secureCharacter(upper),
      secureCharacter(lower),
      secureCharacter(digits),
      secureCharacter(symbols)
    ];
    while (output.length < length) output.push(secureCharacter(alphabet));
    return shuffleSecurely(output).join("");
  }

  function setupPasswordGenerator() {
    document.addEventListener("click", function (event) {
      var button = closest(event.target, "[data-generate-password-for]");
      var input;
      var requestedLength;
      var length;
      var generated;
      var confirmationName;
      var confirmationInput;
      if (!button) return;

      input = document.getElementById(button.getAttribute("data-generate-password-for"));
      if (!input) return;

      if (!window.crypto || typeof window.crypto.getRandomValues !== "function") {
        showToast("Secure password generation is not supported in this browser context.", "error");
        return;
      }

      requestedLength = parseInt(button.getAttribute("data-password-length") || "20", 10);
      length = isNaN(requestedLength) ? 20 : Math.max(16, Math.min(requestedLength, 128));
      generated = generatePassword(length);
      input.value = generated;
      dispatchBubblingEvent(input, "input");
      dispatchBubblingEvent(input, "change");

      confirmationName = input.name === "password"
        ? "confirm_password"
        : (input.name === "new_password" ? "confirm_new_password" : null);
      confirmationInput = confirmationName && input.form
        ? input.form.elements.namedItem(confirmationName)
        : null;
      if (confirmationInput && confirmationInput.tagName === "INPUT") {
        confirmationInput.value = generated;
        dispatchBubblingEvent(confirmationInput, "input");
        dispatchBubblingEvent(confirmationInput, "change");
      }

      focusSafely(input);
      showToast("Secure password generated. Save the form to store it.");
    });
  }

  function fallbackCopy(text) {
    var helper = document.createElement("textarea");
    var succeeded = false;
    helper.value = text;
    helper.setAttribute("readonly", "readonly");
    helper.style.position = "fixed";
    helper.style.left = "-9999px";
    helper.style.top = "0";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.select();
    try {
      succeeded = document.execCommand("copy");
    } catch (_error) {
      succeeded = false;
    }
    removeElement(helper);
    return succeeded;
  }

  function copyText(text, onSuccess, onFailure) {
    if (navigator.clipboard && window.isSecureContext && typeof navigator.clipboard.writeText === "function") {
      try {
        navigator.clipboard.writeText(text).then(onSuccess, function () {
          if (fallbackCopy(text)) onSuccess();
          else onFailure();
        });
      } catch (_error) {
        if (fallbackCopy(text)) onSuccess();
        else onFailure();
      }
      return;
    }
    if (fallbackCopy(text)) onSuccess();
    else onFailure();
  }

  function setupCopyButtons() {
    document.addEventListener("click", function (event) {
      var button = closest(event.target, "[data-copy-target], [data-copy-text]");
      var targetId;
      var target;
      var text;
      if (!button) return;

      targetId = button.getAttribute("data-copy-target");
      target = targetId ? document.getElementById(targetId) : null;
      if (targetId && !target) return;

      if (button.hasAttribute("data-copy-text")) {
        text = button.getAttribute("data-copy-text");
      } else if (target && "value" in target) {
        text = target.value;
      } else {
        text = target ? target.textContent : "";
      }

      if (!text) {
        showToast("There is nothing to copy.", "error");
        return;
      }

      copyText(text, function () {
        showToast(button.getAttribute("data-copy-success") || "Copied to clipboard.");
      }, function () {
        showToast("Could not access the clipboard. Select and copy manually.", "error");
      });
    });
  }

  function getBackupCodes(button) {
    var section = closest(button, ".backup-code-section");
    var nodes;
    var codes = [];
    if (!section) return codes;
    nodes = $$(".backup-code code", section);
    forEach(nodes, function (node) {
      var code = (node.textContent || "").replace(/^\s+|\s+$/g, "");
      if (code) codes.push(code);
    });
    return codes;
  }

  function setupBackupCodeActions() {
    document.addEventListener("click", function (event) {
      var copyButton = closest(event.target, "[data-copy-backup-codes]");
      var downloadButton = closest(event.target, "[data-download-backup-codes]");
      var button = copyButton || downloadButton;
      var codes;
      var content;
      var blob;
      var objectUrl;
      var link;
      if (!button) return;

      codes = getBackupCodes(button);
      if (!codes.length) {
        showToast("No backup codes are available to export.", "error");
        return;
      }

      content = [
        "PassGuard backup codes",
        "Each code can be used once. Store this file somewhere safe and offline.",
        "",
        codes.join("\n"),
        ""
      ].join("\n");

      if (copyButton) {
        copyText(content, function () {
          showToast("Backup codes copied. Store them securely.");
        }, function () {
          showToast("Could not access the clipboard. Use the download option.", "error");
        });
        return;
      }

      if (typeof Blob === "undefined" || !window.URL || !window.URL.createObjectURL) {
        showToast("File download is not supported here. Use Copy all instead.", "error");
        return;
      }

      blob = new Blob([content], { type: "text/plain;charset=utf-8" });
      objectUrl = window.URL.createObjectURL(blob);
      link = document.createElement("a");
      if (!("download" in link)) {
        window.URL.revokeObjectURL(objectUrl);
        showToast("File download is not supported here. Use Copy all instead.", "error");
        return;
      }
      link.href = objectUrl;
      link.download = "passguard-backup-codes.txt";
      link.hidden = true;
      document.body.appendChild(link);
      link.click();
      removeElement(link);
      window.setTimeout(function () { window.URL.revokeObjectURL(objectUrl); }, 1000);
      showToast("Backup codes downloaded. Keep the file private.");
    });
  }

  function setupConfirmations() {
    document.addEventListener("click", function (event) {
      var submitter = closest(event.target, 'button[type="submit"], input[type="submit"]');
      var prompt;
      var form;
      if (!submitter || !submitter.getAttribute("data-confirm")) return;
      prompt = submitter.getAttribute("data-confirm");
      form = submitter.form;
      if (form && window.confirm(prompt)) {
        form.setAttribute("data-confirm-accepted", "true");
      } else if (event.preventDefault) {
        event.preventDefault();
      }
    });

    document.addEventListener("submit", function (event) {
      var form = event.target;
      var submitter = event.submitter || null;
      var prompt;
      if (!form || String(form.tagName).toLowerCase() !== "form") return;
      if (form.getAttribute("data-confirm-accepted") === "true") {
        form.removeAttribute("data-confirm-accepted");
        return;
      }
      prompt = (submitter && submitter.getAttribute("data-confirm")) || form.getAttribute("data-confirm");
      if (prompt && !window.confirm(prompt) && event.preventDefault) event.preventDefault();
    });
  }

  function setupSearchShortcut() {
    document.addEventListener("keydown", function (event) {
      var target = event.target || event.srcElement;
      var tagName = target && target.tagName ? String(target.tagName).toUpperCase() : "";
      var typing = !!(target && (target.isContentEditable || tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT"));
      var search;
      if (typing || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === "/" || event.keyCode === 191) {
        search = $(".topbar-search input[type='search']");
        if (search) {
          if (event.preventDefault) event.preventDefault();
          focusSafely(search);
        }
      }
    });
  }


  function setupPrivatePageRestore() {
    // Back-forward cache can retain rendered credential details in memory.
    // Reloading asks the server to re-check the authenticated session.
    window.addEventListener("pageshow", function (event) {
      if (event && event.persisted) window.location.reload();
    });
  }

  function setupCredentialBulkSelection() {
    var masterCheckbox = $("[data-select-all]");
    var selectedCount = $$("[data-credential-select]");
    var countOutput = $("[data-selected-count]");
    var moveButton = $("[data-bulk-move]");
    var deleteButton = $("[data-bulk-delete]");
    var targetVault = $("#bulkTargetVault");

    function getSelected() {
      var selected = [];
      forEach(selectedCount, function (checkbox) {
        if (checkbox.checked) selected.push(checkbox);
      });
      return selected;
    }

    function synchronize() {
      var selected = getSelected();
      var total = selectedCount.length;
      var checked = selected.length;

      if (countOutput) {
        countOutput.textContent = checked + " selected";
      }
      if (moveButton) moveButton.disabled = checked === 0;
      if (deleteButton) deleteButton.disabled = checked === 0;
      if (masterCheckbox) {
        masterCheckbox.checked = total > 0 && checked === total;
        masterCheckbox.indeterminate = checked > 0 && checked < total;
      }
    }

    if (!selectedCount.length) return;

    forEach(selectedCount, function (checkbox) {
      checkbox.addEventListener("change", synchronize);
    });

    if (masterCheckbox) {
      masterCheckbox.addEventListener("change", function () {
        forEach(selectedCount, function (checkbox) {
          checkbox.checked = masterCheckbox.checked;
        });
        synchronize();
      });
    }

    if (moveButton) {
      moveButton.addEventListener("click", function (event) {
        if (!getSelected().length || !targetVault || !targetVault.value) {
          if (event.preventDefault) event.preventDefault();
          showToast("Select credentials and a destination vault first.", "error");
        }
      });
    }

    if (deleteButton) {
      deleteButton.addEventListener("click", function (event) {
        if (!getSelected().length) {
          if (event.preventDefault) event.preventDefault();
          showToast("Select at least one credential first.", "error");
        }
      });
    }

    synchronize();
  }

  function initialize() {
    setupSidebar();
    setupMessageDismissal();
    setupPasswordVisibility();
    setupCredentialPasswordReveal();
    setupPasswordGenerator();
    setupCopyButtons();
    setupBackupCodeActions();
    setupConfirmations();
    setupSearchShortcut();
    setupCredentialBulkSelection();
    setupPrivatePageRestore();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }
}());
