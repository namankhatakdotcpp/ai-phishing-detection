// Injected into the active tab via chrome.scripting.executeScript after the
// user explicitly clicks "Analyze this page" (activeTab permission — no
// persistent access, no background scanning). Computes the exact same
// feature schema as the Python pipeline
// (phishshield.features.url_features / html_features) so the browser-side
// vector matches the trained model's input distribution, then returns a
// flat {feature_name: value} object as the script's completion value.
//
// This only ever reads page structure (form/input counts, script/action
// domains, title text, inline hidden-element styles) and the URL string.
// It never reads form field values, so no credentials the user has typed
// are collected or sent anywhere.

(function extractPageFeatures() {
  const SPECIAL_CHARS = new Set("~!@#$%^&*()_+={}[]|\\:;\"'<>,?".split(""));
  const SUSPICIOUS_TLDS = new Set(["zip", "mov", "top", "xyz", "click", "gq", "tk", "ml", "cf", "ga"]);
  const KNOWN_BRANDS = new Set([
    "paypal", "amazon", "apple", "microsoft", "google", "chase",
    "wellsfargo", "bankofamerica", "netflix", "facebook", "instagram",
    "outlook", "office365", "dropbox", "linkedin", "coinbase",
  ]);

  function isIpLiteral(host) {
    const h = host.replace(/^\[|\]$/g, "");
    if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(h)) {
      return h.split(".").every((octet) => Number(octet) >= 0 && Number(octet) <= 255);
    }
    // crude IPv6 literal check: hex groups separated by ':'
    return /^[0-9a-fA-F:]+$/.test(h) && h.includes(":");
  }

  function registrableParts(host) {
    return host.split(".").filter(Boolean);
  }

  function registrableDomain(url) {
    let host = "";
    try {
      host = new URL(url).hostname.toLowerCase();
    } catch {
      return "";
    }
    const parts = registrableParts(host);
    if (parts.length < 2) return parts.join("");
    return parts[parts.length - 2];
  }

  function extractUrlFeatures(rawUrl) {
    const features = {
      url_length: 0, num_dots: 0, num_hyphens: 0, num_subdomains: 0,
      num_digits: 0, digit_ratio: 0.0, special_char_count: 0, special_char_ratio: 0.0,
      has_at_symbol: 0, has_ip_literal: 0, is_https: 0, path_length: 0,
      query_length: 0, has_suspicious_tld: 0, has_port: 0, is_parsable: 1,
    };

    const url = (rawUrl || "").trim();
    features.url_length = url.length;
    if (!url) {
      features.is_parsable = 0;
      return features;
    }

    let parsed;
    try {
      parsed = new URL(url.includes("://") ? url : `http://${url}`);
    } catch {
      features.is_parsable = 0;
      return features;
    }

    const host = parsed.hostname || "";
    features.num_dots = (url.match(/\./g) || []).length;
    features.num_hyphens = (url.match(/-/g) || []).length;
    features.has_at_symbol = url.includes("@") ? 1 : 0;
    features.is_https = parsed.protocol === "https:" ? 1 : 0;
    features.path_length = (parsed.pathname || "").length;
    features.query_length = (parsed.search || "").replace(/^\?/, "").length;
    features.has_port = parsed.port ? 1 : 0;

    const digits = (url.match(/\d/g) || []).length;
    features.num_digits = digits;
    features.digit_ratio = url.length ? digits / url.length : 0.0;

    let special = 0;
    for (const ch of url) if (SPECIAL_CHARS.has(ch)) special += 1;
    features.special_char_count = special;
    features.special_char_ratio = url.length ? special / url.length : 0.0;

    if (host) {
      features.has_ip_literal = isIpLiteral(host) ? 1 : 0;
      const hostParts = registrableParts(host);
      features.num_subdomains = Math.max(0, hostParts.length - 2);
      const tld = hostParts.length ? hostParts[hostParts.length - 1].toLowerCase() : "";
      features.has_suspicious_tld = SUSPICIOUS_TLDS.has(tld) ? 1 : 0;
    }

    return features;
  }

  function externalDomains(elements, attr, pageDomain) {
    const domains = new Set();
    for (const el of elements) {
      const src = el.getAttribute(attr);
      if (!src || !/^(https?:)?\/\//.test(src)) continue;
      let host = "";
      try {
        host = new URL(src, location.href).hostname.toLowerCase();
      } catch {
        continue;
      }
      const parts = registrableParts(host);
      const domain = parts.length >= 2 ? parts[parts.length - 2] : host;
      if (domain && domain !== pageDomain) domains.add(domain);
    }
    return domains;
  }

  function isHidden(el) {
    const style = (el.getAttribute("style") || "").replace(/\s+/g, "").toLowerCase();
    return style.includes("display:none") || style.includes("visibility:hidden");
  }

  function extractHtmlFeatures(pageUrl) {
    const features = {
      has_html: 1, num_forms: 0, num_password_fields: 0, num_text_input_fields: 0,
      num_iframes: 0, num_external_js_domains: 0, num_external_form_actions: 0,
      has_external_form_action: 0, title_brand_mismatch: 0, num_hidden_elements: 0,
      has_favicon_mismatch: 0,
    };

    const pageDomain = registrableDomain(pageUrl);
    const forms = Array.from(document.querySelectorAll("form"));

    features.num_forms = forms.length;
    features.num_password_fields = document.querySelectorAll('input[type="password"]').length;
    features.num_text_input_fields = document.querySelectorAll('input[type="text"], input[type="email"]').length;
    features.num_iframes = document.querySelectorAll("iframe").length;

    features.num_external_js_domains = externalDomains(
      document.querySelectorAll("script[src]"), "src", pageDomain
    ).size;

    let externalActions = 0;
    for (const form of forms) {
      const action = form.getAttribute("action") || "";
      if (/^https?:\/\//.test(action)) {
        let actionHost = "";
        try {
          actionHost = new URL(action).hostname.toLowerCase();
        } catch {
          continue;
        }
        const parts = registrableParts(actionHost);
        const actionDomain = parts.length >= 2 ? parts[parts.length - 2] : actionHost;
        if (pageDomain && actionDomain !== pageDomain) externalActions += 1;
      }
    }
    features.num_external_form_actions = externalActions;
    features.has_external_form_action = externalActions > 0 ? 1 : 0;

    const title = (document.title || "").toLowerCase();
    const mentionedBrands = [...KNOWN_BRANDS].filter((b) => title.includes(b));
    if (mentionedBrands.length && !mentionedBrands.includes(pageDomain)) {
      features.title_brand_mismatch = 1;
    }

    features.num_hidden_elements = Array.from(document.querySelectorAll("*")).filter(isHidden).length;

    return features;
  }

  const pageUrl = location.href;
  return {
    ...extractUrlFeatures(pageUrl),
    ...extractHtmlFeatures(pageUrl),
    _meta_url: pageUrl,
    _meta_title: document.title || "",
  };
})();
