# services/auth-service/app/schemas/auth.py

from agriculture_ai.types.schemas import (LoginRequest, TokenResponse, UserCreate, UserResponse, ChangePasswordRequest, ResetPasswordRequest, ForgotPasswordRequest, VerifyEmailRequest, ResendVerificationRequest, UpdateProfileRequest, RefreshTokenRequest
, TwoFactorSetupResponse,TwoFactorVerifyRequest, TwoFactorDisableRequest,
APIKeyCreate, APIKeyResponse, SessionResponse, OAuthAuthorizeRequest, OAuthAccountResponse, LogoutRequest)

UserUpdate = UpdateProfileRequest
