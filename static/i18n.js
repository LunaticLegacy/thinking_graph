class I18n {
    constructor({ defaultLanguage = "zh", supportedLanguages = ["zh", "en"] } = {}) {
        this.defaultLanguage = defaultLanguage;
        this.currentLanguage = defaultLanguage;
        this.supportedLanguages = new Set(supportedLanguages);
        this.translations = {};
        this.ready = this.init();
    }

    async init() {
        const languagesToPreload = Array.from(this.supportedLanguages);
        await Promise.all(languagesToPreload.map((lang) => this.loadLanguage(lang)));

        const preferredLanguage = this.resolveInitialLanguage();
        await this.setLanguage(preferredLanguage, { persist: false, emit: false });

        this.bindLanguageSwitcher();
        this.emitLanguageChanged();
    }

    resolveInitialLanguage() {
        const localStored = localStorage.getItem("lang");
        if (localStored) {
            return this.normalizeLanguage(localStored);
        }

        const browserLanguage = (navigator.language || this.defaultLanguage).split("-")[0];
        return this.normalizeLanguage(browserLanguage);
    }

    normalizeLanguage(language) {
        const normalized = (language || "").toLowerCase();
        if (this.supportedLanguages.has(normalized)) {
            return normalized;
        }
        return this.defaultLanguage;
    }

    async loadLanguage(language) {
        const normalized = this.normalizeLanguage(language);
        if (this.translations[normalized]) {
            return this.translations[normalized];
        }

        try {
            const response = await fetch(`/static/locales/${normalized}.json`, { cache: "no-cache" });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            this.translations[normalized] = data;
            return data;
        } catch (error) {
            console.error(`Failed to load language file: ${normalized}`, error);
            this.translations[normalized] = {};
            return this.translations[normalized];
        }
    }

    getNestedValue(source, key) {
        return key.split(".").reduce((acc, segment) => {
            if (acc && Object.prototype.hasOwnProperty.call(acc, segment)) {
                return acc[segment];
            }
            return undefined;
        }, source);
    }

    t(key, params = {}) {
        const activeValue = this.getNestedValue(this.translations[this.currentLanguage], key);
        const fallbackValue = this.getNestedValue(this.translations[this.defaultLanguage], key);
        const resolved = activeValue ?? fallbackValue;

        if (typeof resolved !== "string") {
            return key;
        }

        return this.replacePlaceholders(resolved, params);
    }

    replacePlaceholders(template, params = {}) {
        return template.replace(/%(\w+)%/g, (match, name) => {
            if (Object.prototype.hasOwnProperty.call(params, name)) {
                return params[name];
            }
            return match;
        });
    }

    extractI18nParams(element) {
        const params = {};
        for (const attr of Array.from(element.attributes)) {
            if (!attr.name.startsWith("data-i18n-")) {
                continue;
            }

            const key = attr.name.substring("data-i18n-".length);
            if (key === "placeholder" || key === "aria-label") {
                continue;
            }

            params[key] = attr.value;
        }
        return params;
    }

    updatePageText() {
        const textElements = document.querySelectorAll("[data-i18n]");
        for (const element of textElements) {
            const key = element.getAttribute("data-i18n");
            if (!key) {
                continue;
            }
            const params = this.extractI18nParams(element);
            element.textContent = this.t(key, params);
        }

        const placeholderElements = document.querySelectorAll("[data-i18n-placeholder]");
        for (const element of placeholderElements) {
            const key = element.getAttribute("data-i18n-placeholder");
            if (!key) {
                continue;
            }
            const params = this.extractI18nParams(element);
            element.placeholder = this.t(key, params);
        }

        const ariaLabelElements = document.querySelectorAll("[data-i18n-aria-label]");
        for (const element of ariaLabelElements) {
            const key = element.getAttribute("data-i18n-aria-label");
            if (!key) {
                continue;
            }
            element.setAttribute("aria-label", this.t(key));
        }

        document.title = this.t("appTitle");
    }

    bindLanguageSwitcher() {
        const selector = document.getElementById("language-selector");
        if (!selector) {
            return;
        }

        selector.addEventListener("change", async (event) => {
            const target = event.target;
            await this.setLanguage(target.value);
        });

        this.syncLanguageSwitcher();
    }

    syncLanguageSwitcher() {
        const selector = document.getElementById("language-selector");
        if (!selector) {
            return;
        }
        selector.value = this.currentLanguage;
    }

    emitLanguageChanged() {
        document.dispatchEvent(
            new CustomEvent("i18n:changed", {
                detail: { language: this.currentLanguage },
            })
        );
    }

    async setLanguage(language, { persist = true, emit = true } = {}) {
        const normalized = this.normalizeLanguage(language);

        if (!this.translations[normalized]) {
            await this.loadLanguage(normalized);
        }

        this.currentLanguage = normalized;

        if (persist) {
            localStorage.setItem("lang", normalized);
        }

        document.documentElement.lang = normalized === "zh" ? "zh-CN" : normalized;

        this.syncLanguageSwitcher();
        this.updatePageText();

        if (emit) {
            this.emitLanguageChanged();
        }
    }

    getCurrentLanguage() {
        return this.currentLanguage;
    }
}

window.i18n = new I18n();
