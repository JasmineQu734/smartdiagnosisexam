import axios from 'axios';

// 统一 API 客户端：身份由登录接口签发的令牌承载，请求时放进 Authorization 头。
// 后端 AuthFilter 校验令牌并把身份投影给 RoleInterceptor，请求头不再携带可伪造的 X-Role / X-User。
export const api = axios.create({ baseURL: '/api/v1' });

let current = { token: '' };

export const setApiUser = (user) => {
  current = { token: (user && user.token) || '' };
};

api.interceptors.request.use((config) => {
  config.headers = config.headers || {};
  if (current.token) config.headers['Authorization'] = 'Bearer ' + current.token;
  return config;
});

// 令牌失效（401）：丢掉本地身份并回到登录页，避免界面停在半截状态或拿旧身份继续请求。
// 登录接口自身的 401 是「账号不存在」，不能触发刷新，否则会把刚填的账号清掉。
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = (error.config && error.config.url) || '';
    if (error.response && error.response.status === 401 && !url.includes('/auth/login')) {
      current = { token: '' };
      if (typeof window !== 'undefined') window.location.reload();
    }
    return Promise.reject(error);
  },
);

export const getData = (url, fallback = null) => api.get(url)
  .then((response) => (response.data && response.data.code === 0 ? response.data.data : fallback))
  .catch((error) => { console.warn('[api] 请求失败，本次按兜底值展示：', url, error && error.message); return fallback; });

export const postData = (url, body, fallback = null) => api.post(url, body)
  .then((response) => (response.data && response.data.code === 0 ? response.data.data : fallback))
  .catch((error) => { console.warn('[api] 请求失败，本次按兜底值展示：', url, error && error.message); return fallback; });

// 统一文档下载：先取回二进制再落盘，后端返回 404 等错误时直接抛出，
// 避免浏览器把错误响应悄悄存成内容损坏的 .pdf / .docx。
export const downloadFile = async (url, fileName) => {
  const path = url && url.startsWith('/api/v1') ? url.slice('/api/v1'.length) : url;
  const response = await api.get(path, { responseType: 'blob' });
  const objectUrl = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(objectUrl);
};
