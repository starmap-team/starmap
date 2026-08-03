# Phase 12 — 管理后台模块 (Admin + AuditLog + UserManagement) 研究报告

## 模块概述

管理后台模块，包含 3 个子页面：Admin, AuditLog, UserManagement。

## 关键文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `frontend/src/pages/Admin.vue` | 769 行 | 管理后台主页 |
| `frontend/src/pages/AuditLog.vue` | 226 行 | 审计日志 |
| `frontend/src/pages/UserManagement.vue` | 553 行 | 用户管理 |
| `frontend/src/pages/__tests__/Admin.spec.ts` | 44 行 | 1 个冒烟测试 |
| `frontend/src/pages/__tests__/AuditLog.spec.ts` | 44 行 | 1 个冒烟测试 |
| `frontend/src/pages/__tests__/UserManagement.spec.ts` | 45 行 | 1 个冒烟测试 |

## 后端 API 端点

### 用户管理 (`/api/v1/admin/users`)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/admin/users` | GET | 用户列表 |
| `/admin/users` | POST | 创建用户 |
| `/admin/users/{user_id}` | GET | 用户详情 |
| `/admin/users/{user_id}` | PATCH | 更新用户 |
| `/admin/users/{user_id}` | DELETE | 删除用户 |
| `/admin/users/{user_id}/unlock` | POST | 解锁用户 |
| `/admin/users/{user_id}/reset-password` | POST | 重置密码 |

### 审计日志 (`/api/v1/admin/audit-events`)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/admin/audit-events` | GET | 审计事件列表 |

## 测试覆盖现状

- 3 个冒烟测试（每个页面 1 个）
