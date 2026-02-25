// 国际化管理类
class I18n {
  constructor() {
    this.currentLanguage = 'zh';
    this.translations = {};
    this.defaultLanguage = 'zh';
    this.init();
  }

  async init() {
    await this.loadLanguage(this.defaultLanguage);
    await this.loadLanguage('en');
    
    // 检测用户语言偏好
    const userLang = localStorage.getItem('lang') || 
                     navigator.language.split('-')[0] || 
                     this.defaultLanguage;
    
    if (this.translations[userLang]) {
      this.setLanguage(userLang);
    } else {
      this.setLanguage(this.defaultLanguage);
    }
  }

  async loadLanguage(lang) {
    if (this.translations[lang]) {
      return this.translations[lang];
    }

    try {
      const response = await fetch(`./static/locales/${lang}.json`);
      const data = await response.json();
      this.translations[lang] = data;
      return data;
    } catch (error) {
      console.error(`Failed to load language file for ${lang}:`, error);
      return {};
    }
  }

  async setLanguage(lang) {
    if (!this.translations[lang]) {
      await this.loadLanguage(lang);
    }

    this.currentLanguage = lang;
    localStorage.setItem('lang', lang);
    
    // 更新HTML语言属性
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : lang;
    
    // 更新页面文本
    this.updatePageText();
  }

  t(key, params = {}) {
    const keys = key.split('.');
    let value = this.translations[this.currentLanguage];
    
    for (const k of keys) {
      if (value && value.hasOwnProperty(k)) {
        value = value[k];
      } else {
        console.warn(`Translation key not found: ${key}`);
        return key; // 返回原始键名作为fallback
      }
    }

    // 如果有参数，替换占位符
    if (typeof value === 'string' && Object.keys(params).length > 0) {
      return this.replacePlaceholders(value, params);
    }

    return value;
  }

  replacePlaceholders(str, params) {
    return str.replace(/%(\w+)%/g, (match, key) => {
      return params[key] !== undefined ? params[key] : match;
    });
  }

  updatePageText() {
    // 更新所有带有data-i18n属性的元素
    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(el => {
      const key = el.getAttribute('data-i18n');
      const params = this.extractParams(el);
      const translatedText = this.t(key, params);
      
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = translatedText;
      } else if (el.tagName === 'OPTION') {
        el.textContent = translatedText;
      } else {
        el.textContent = translatedText;
      }
    });
    
    // 更新页面标题
    document.title = this.t('appTitle');
  }

  extractParams(element) {
    const params = {};
    const paramAttrs = Array.from(element.attributes)
      .filter(attr => attr.name.startsWith('data-i18n-'))
      .map(attr => {
        const key = attr.name.substring(10); // 移除 'data-i18n-' 前缀
        params[key] = attr.value;
        return { key, value: attr.value };
      });
    
    return params;
  }

  getCurrentLanguage() {
    return this.currentLanguage;
  }
}

// 创建全局实例
const i18n = new I18n();

// 初始化语言切换器
function initLanguageSwitcher() {
  // 添加语言切换按钮
  const header = document.querySelector('.topbar div');
  if (header) {
    const switcher = document.createElement('div');
    switcher.className = 'language-switcher';
    switcher.innerHTML = `
      <select id="language-selector" onchange="changeLanguage()">
        <option value="zh" ${i18n.getCurrentLanguage() === 'zh' ? 'selected' : ''}>中文</option>
        <option value="en" ${i18n.getCurrentLanguage() === 'en' ? 'selected' : ''}>English</option>
      </select>
    `;
    header.appendChild(switcher);
  }
}

function changeLanguage() {
  const selector = document.getElementById('language-selector');
  const lang = selector.value;
  i18n.setLanguage(lang);
}

// 在DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    initLanguageSwitcher();
  }, 100); // 稍微延迟确保DOM完全渲染
});