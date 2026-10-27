/**
 * API配置文件
 * 包含API基础URL和旅行助手功能所需的API参数
 */

// API基础URL配置
export const apiConfig = {
  // 后端API基础URL
  baseURL: 'http://127.0.0.1:8000',
}

export const aiChatConfig = {
  // 旅行助手后端接口（合并后的 FastAPI 服务）
  apiEndpoint: `${apiConfig.baseURL}/api/travel/chat`,
}