# Web de la demo: bucket privado + CloudFront (HTTPS, sin costo fijo). La web es estática y
# habla directamente con Cognito y con la API; su configuración (config.js) la genera Terraform.

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled" # sitio diminuto: sin caché, los cambios se ven al instante
}

resource "aws_s3_bucket" "web" {
  # checkov:skip=CKV_AWS_144:Sin replicación; el sitio se regenera desde este repositorio
  # checkov:skip=CKV_AWS_145:SSE-S3; una CMK añade costo fijo (NFR-012)
  # checkov:skip=CKV_AWS_18:Sin access logging; requeriría otro bucket solo para la demo
  # checkov:skip=CKV2_AWS_61:Sin lifecycle; el sitio pesa unos KB y se destruye con el entorno
  # checkov:skip=CKV2_AWS_62:Sin notificaciones; nadie consume eventos del bucket
  # checkov:skip=CKV_AWS_21:Sin versionado; el contenido es una copia regenerable del repositorio
  bucket        = "${local.name}-web-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "web" {
  bucket                  = aws_s3_bucket.web.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "web" {
  bucket = aws_s3_bucket.web.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "${local.name}-web"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Solo CloudFront puede leer el bucket.
resource "aws_s3_bucket_policy" "web" {
  bucket = aws_s3_bucket.web.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.web.arn}/*"
      Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.web.arn } }
    }]
  })
}

resource "aws_cloudfront_response_headers_policy" "web" {
  name = "${local.name}-web-security"

  security_headers_config {
    # La web solo carga lo suyo y solo habla con Cognito y con la API.
    content_security_policy {
      override                = true
      content_security_policy = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self' https://*.execute-api.${var.region}.amazonaws.com https://cognito-idp.${var.region}.amazonaws.com; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    }
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "no-referrer"
      override        = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
  }
}

resource "aws_cloudfront_distribution" "web" {
  # checkov:skip=CKV_AWS_68:Sin WAF: costo fijo mensual; el tráfico lo acotan las cuotas y el throttling de la API (NFR-012)
  # checkov:skip=CKV_AWS_86:Sin access logging; requeriría otro bucket solo para la demo
  # checkov:skip=CKV_AWS_310:Un solo origen: el sitio es estático y se regenera desde este repositorio
  # checkov:skip=CKV_AWS_374:Sin restricción geográfica: la charla puede seguirse desde cualquier país
  # checkov:skip=CKV2_AWS_47:Sin WAF; ver CKV_AWS_68
  # checkov:skip=CKV2_AWS_42:Sin dominio propio: se usa el certificado por defecto de CloudFront (*.cloudfront.net)
  # checkov:skip=CKV_AWS_174:Con el certificado por defecto de CloudFront la versión mínima de TLS no es configurable
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Pregúntale al repo"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  origin {
    domain_name              = aws_s3_bucket.web.bucket_regional_domain_name
    origin_id                = "web"
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id
  }

  default_cache_behavior {
    target_origin_id           = "web"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.web.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

locals {
  web_content_types = {
    html = "text/html; charset=utf-8"
    css  = "text/css; charset=utf-8"
    js   = "text/javascript; charset=utf-8"
    svg  = "image/svg+xml"
    png  = "image/png"
  }
  web_files = setsubtract(fileset("${path.module}/../web", "*.{html,css,js,svg,png}"), ["config.js", "config.example.js"])
}

resource "aws_s3_object" "web" {
  for_each = local.web_files

  bucket        = aws_s3_bucket.web.id
  key           = each.value
  source        = "${path.module}/../web/${each.value}"
  etag          = filemd5("${path.module}/../web/${each.value}")
  content_type  = local.web_content_types[reverse(split(".", each.value))[0]]
  cache_control = "no-cache"
}

# Valores reales de esta instalación; el navegador los lee antes de arrancar la app.
resource "aws_s3_object" "web_config" {
  bucket        = aws_s3_bucket.web.id
  key           = "config.js"
  content_type  = "text/javascript; charset=utf-8"
  cache_control = "no-cache"
  content = "window.APP_CONFIG = ${jsonencode({
    apiUrl   = aws_apigatewayv2_api.main.api_endpoint
    clientId = aws_cognito_user_pool_client.web.id
    region   = var.region
  })};\n"
}
