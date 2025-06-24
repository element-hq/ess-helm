#!/bin/bash

# Matrix Server Deployment Setup Script

# 色彩定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CONFIG_FILE="config.sh"
CONFIG_TEMPLATE="config.sh.template"

# 函数：打印错误信息并退出
error_exit() {
    echo -e "${RED}错误: $1${NC}" >&2
    exit 1
}

# 函数：打印成功信息
success_msg() {
    echo -e "${GREEN}$1${NC}"
}

# 函数：打印警告信息
warning_msg() {
    echo -e "${YELLOW}$1${NC}"
}

# 函数：打印信息
info_msg() {
    echo -e "${BLUE}$1${NC}"
}

# 函数：读取用户输入，提供默认值
# 参数1: 提示信息
# 参数2: 变量名 (用于config.sh中的占位符替换)
# 参数3: 默认值
# 参数4: (可选) 验证函数名
prompt_user() {
    local prompt_text="$1"
    local var_name="$2"
    local default_value="$3"
    local validation_func="$4"
    local current_value=""
    local input=""

    # 从模板中提取占位符对应的当前值（如果config.sh已存在且该行已定义）
    if [ -f "$CONFIG_FILE" ] && grep -q "^${var_name}=" "$CONFIG_FILE"; then
        current_value=$(grep "^${var_name}=" "$CONFIG_FILE" | head -n 1 | cut -d'=' -f2 | tr -d '"')
    fi

    # 如果当前值为空，则使用默认值作为提示
    if [ -z "$current_value" ]; then
        current_value="$default_value"
    fi

    while true; do
        if [ -n "$current_value" ]; then
            read -r -p "$(echo -e "${prompt_text} [默认: ${YELLOW}${current_value}${NC}]: ")" input
        else # 适用于没有current_value（首次运行或该变量未在旧config中定义）的情况
             if [ -n "$default_value" ]; then
                read -r -p "$(echo -e "${prompt_text} [默认: ${YELLOW}${default_value}${NC}]: ")" input
             else
                read -r -p "$(echo -e "${prompt_text} [无默认值]: ")" input
             fi
        fi

        input="${input:-$current_value}"
        input="${input:-$default_value}"

        if [ -n "$validation_func" ]; then
            if "$validation_func" "$input"; then
                break
            else
                warning_msg "输入无效，请重试。"
            fi
        else
            break # 无验证函数则直接通过
        fi
    done

    # 使用 awk 更新 config.sh 文件以提高稳健性
    # 如果行存在，则替换；如果不存在，则追加 (但模板应该包含所有行，所以主要是替换)
    # 注意：这里的 awk 逻辑假设 %%VAR_NAME%% 占位符存在于模板中
    awk -v var="%%${var_name}%%" -v val="${input}" '{gsub(var, val); print}' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"


    # 如果变量是DOMAIN，额外更新依赖DOMAIN的变量
    if [ "$var_name" == "DOMAIN" ]; then
        local domain_val="$input" # 使用当前输入的DOMAIN值
        awk -v val="acme@${domain_val}" '{gsub(/acme@%%DOMAIN%%/, val); print}' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"

        # 更新 FULL_X_DOMAIN 中的 %%DOMAIN%% 部分
        local matrix_sub_placeholder="%%MATRIX_SUBDOMAIN%%"
        local element_sub_placeholder="%%ELEMENT_SUBDOMAIN%%"
        local rtc_sub_placeholder="%%RTC_SUBDOMAIN%%"
        local mas_sub_placeholder="%%MAS_SUBDOMAIN%%"
        local turn_sub_placeholder="%%TURN_SUBDOMAIN%%"

        awk -v val=".${domain_val}" \
            -v msp="${matrix_sub_placeholder}" \
            -v esp="${element_sub_placeholder}" \
            -v rsp="${rtc_sub_placeholder}" \
            -v asp="${mas_sub_placeholder}" \
            -v tsp="${turn_sub_placeholder}" \
            '{
                sub(msp "\\.%%DOMAIN%%", msp val);
                sub(esp "\\.%%DOMAIN%%", esp val);
                sub(rsp "\\.%%DOMAIN%%", rsp val);
                sub(asp "\\.%%DOMAIN%%", asp val);
                sub(tsp "\\.%%DOMAIN%%", tsp val);
                print;
            }' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
    fi

    # 如果变量是特定的子域名，也需要更新对应的 FULL_X_DOMAIN
    if [[ "$var_name" == "MATRIX_SUBDOMAIN" || \
          "$var_name" == "ELEMENT_SUBDOMAIN" || \
          "$var_name" == "RTC_SUBDOMAIN" || \
          "$var_name" == "MAS_SUBDOMAIN" || \
          "$var_name" == "TURN_SUBDOMAIN" ]]; then

        local domain_val=$(grep "^DOMAIN=" "$CONFIG_FILE" | head -n 1 | cut -d'=' -f2 | tr -d '"')
        if [ -z "$domain_val" ] || [[ "$domain_val" == "%%DOMAIN%%" ]]; then # 确保DOMAIN已设置
             warning_msg "主域名尚未设置，请先设置主域名。" # 理论上DOMAIN会先被提问
        else
            local sub_val="$input"
            local full_domain_var_name=""
            if [ "$var_name" == "MATRIX_SUBDOMAIN" ]; then full_domain_var_name="FULL_MATRIX_DOMAIN"; fi
            if [ "$var_name" == "ELEMENT_SUBDOMAIN" ]; then full_domain_var_name="FULL_ELEMENT_DOMAIN"; fi
            if [ "$var_name" == "RTC_SUBDOMAIN" ]; then full_domain_var_name="FULL_RTC_DOMAIN"; fi
            if [ "$var_name" == "MAS_SUBDOMAIN" ]; then full_domain_var_name="FULL_MAS_DOMAIN"; fi
            if [ "$var_name" == "TURN_SUBDOMAIN" ]; then full_domain_var_name="FULL_TURN_DOMAIN"; fi

            if [ -n "$full_domain_var_name" ]; then
                 awk -v var_name_line="^${full_domain_var_name}=" -v val_line="${full_domain_var_name}=\"${sub_val}.${domain_val}\"" \
                    '{if ($0 ~ var_name_line) print val_line; else print}' \
                    "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
            fi
        fi
    fi
}


# --- 验证函数 ---
is_valid_ip() {
    if [[ "$1" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        OIFS=$IFS IFS='.' read -r -a parts <<< "$1" IFS=$OIFS
        for part in "${parts[@]}"; do
            if ! [[ "$part" =~ ^[0-9]+$ ]] || [ "$part" -gt 255 ]; then return 1; fi
        done
        return 0 # true
    else
        return 1 # false
    fi
}

is_valid_domain() {
    if [[ "$1" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$ ]]; then
        return 0
    else
        return 1
    fi
}

is_valid_port() {
    if [[ "$1" =~ ^[0-9]+$ ]] && [ "$1" -ge 1 ] && [ "$1" -le 65535 ]; then
        return 0
    else
        return 1
    fi
}

is_not_empty() {
    if [ -n "$1" ]; then
        return 0
    else
        return 1
    fi
}

is_staging_or_production() {
    if [ "$1" == "staging" ] || [ "$1" == "production" ]; then
        return 0
    else
        return 1
    fi
}

# --- 主要逻辑 ---
check_dependencies() {
    info_msg "正在检查依赖项..."
    local missing_deps=0
    for cmd in curl grep sed awk python3; do # pip3 稍后单独检查
        if ! command -v "$cmd" &> /dev/null; then
            warning_msg "依赖 '$cmd' 未找到."
            missing_deps=$((missing_deps + 1))
        fi
    done
    # 检查 python3 -m pip 是否可用
    if ! python3 -m pip --version &> /dev/null; then
        warning_msg "Python3 pip模块 (python3 -m pip) 未找到或无法执行."
        missing_deps=$((missing_deps + 1))
    fi

    if [ "$missing_deps" -gt 0 ]; then
        error_exit "请先安装缺失的依赖项再继续。"
    fi
    success_msg "所有基本依赖项均已满足。"
}

welcome_message() {
    echo -e "${GREEN}=======================================================${NC}"
    echo -e "${GREEN}欢迎使用 Matrix 服务器一键部署脚本 (基于 ess-helm) ${NC}"
    echo -e "${GREEN}=======================================================${NC}"
    echo "此脚本将引导您完成配置过程。"
    echo "请准备好以下信息："
    echo " - 您的主域名 (例如: example.com)"
    echo " - 外部服务器的公网IP地址 (用于 well-known)"
    echo " - 内部K3s服务器的内网IP地址"
    echo " - RouterOS的IP地址、API用户名和密码"
    echo " - Cloudflare API Token"
    echo ""
    echo "您可以随时按 Ctrl+C 中断安装。"
    echo "如果配置文件 '$CONFIG_FILE' 已存在，脚本将加载现有值作为默认值。"
    echo ""
}

# --- 配置收集函数 ---
collect_configurations() {
    info_msg "\n--- 域名配置 ---"
    prompt_user "请输入您的主域名 (例如: example.com)" DOMAIN "" is_valid_domain
    prompt_user "请输入 Synapse API 子域名" MATRIX_SUBDOMAIN "matrix" is_not_empty
    prompt_user "请输入 Element Web 子域名" ELEMENT_SUBDOMAIN "chat" is_not_empty
    prompt_user "请输入 Matrix RTC (LiveKit) 子域名" RTC_SUBDOMAIN "rtc" is_not_empty
    prompt_user "请输入 Matrix Auth Service (MAS) 子域名" MAS_SUBDOMAIN "mas" is_not_empty
    prompt_user "请输入 TURN 服务器子域名" TURN_SUBDOMAIN "turn" is_not_empty

    info_msg "\n--- 服务器IP配置 ---"
    prompt_user "请输入外部服务器的公网IP (用于 well-known)" EXTERNAL_SERVER_IP "" is_valid_ip
    prompt_user "请输入内部K3s服务器的内网IP" INTERNAL_SERVER_IP "" is_valid_ip

    # K3S_NODE_IP 将在 config.sh 中自动设置为 INTERNAL_SERVER_IP 的值
    local internal_ip_val=$(grep "^INTERNAL_SERVER_IP=" "$CONFIG_FILE" | head -n 1 | cut -d'=' -f2 | tr -d '"')
    awk -v val="${internal_ip_val}" '{gsub(/%%K3S_NODE_IP%%/, val); print}' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"


    info_msg "\n--- 外网端口配置 (RouterOS 端口转发的目标外部端口) ---"
    prompt_user "请输入所有子域名HTTPS转发端口" HTTPS_PORT "3443" is_valid_port
    prompt_user "请输入Matrix Federation转发端口" FEDERATION_PORT "8448" is_valid_port
    prompt_user "请输入WebRTC TCP转发端口" WEBRTC_TCP_PORT "33881" is_valid_port
    prompt_user "请输入WebRTC UDP Mux转发端口" UDP_MUX_PORT "33882" is_valid_port
    prompt_user "请输入TURN UDP转发端口" TURN_UDP_PORT "3478" is_valid_port
    prompt_user "请输入TURN TLS转发端口" TURN_TLS_PORT "5349" is_valid_port
    prompt_user "请输入WebRTC UDP端口范围开始" UDP_PORT_RANGE_START "33152" is_valid_port
    prompt_user "请输入WebRTC UDP端口范围结束" UDP_PORT_RANGE_END "33352" is_valid_port

    info_msg "\n--- 内网NodePort配置 (Kubernetes Service NodePort) ---"
    prompt_user "请输入内部HTTPS NodePort" INTERNAL_HTTPS_PORT "30443" is_valid_port
    prompt_user "请输入内部Federation NodePort" INTERNAL_FEDERATION_PORT "30448" is_valid_port
    prompt_user "请输入内部WebRTC TCP NodePort" INTERNAL_WEBRTC_TCP_PORT "30881" is_valid_port
    prompt_user "请输入内部WebRTC UDP Mux NodePort" INTERNAL_UDP_MUX_PORT "30882" is_valid_port
    prompt_user "请输入内部TURN UDP NodePort" INTERNAL_TURN_UDP_PORT "30478" is_valid_port
    prompt_user "请输入内部TURN TLS NodePort" INTERNAL_TURN_TLS_PORT "30349" is_valid_port

    local default_internal_udp_start=$(grep "^UDP_PORT_RANGE_START=" "$CONFIG_FILE" | head -n 1 | cut -d'=' -f2 | tr -d '"')
    local default_internal_udp_end=$(grep "^UDP_PORT_RANGE_END=" "$CONFIG_FILE" | head -n 1 | cut -d'=' -f2 | tr -d '"')
    prompt_user "请输入内部WebRTC UDP范围开始NodePort" INTERNAL_UDP_PORT_RANGE_START "$default_internal_udp_start" is_valid_port
    prompt_user "请输入内部WebRTC UDP范围结束NodePort" INTERNAL_UDP_PORT_RANGE_END "$default_internal_udp_end" is_valid_port


    info_msg "\n--- RouterOS API 配置 ---"
    prompt_user "请输入RouterOS的IP地址" ROUTEROS_IP "" is_valid_ip
    prompt_user "请输入RouterOS API用户名" ROUTEROS_USERNAME "admin" is_not_empty
    read -s -r -p "请输入RouterOS API密码: " routeros_password_input
    echo
    awk -v val="${routeros_password_input}" '{gsub(/%%ROUTEROS_PASSWORD%%/, val); print}' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
    prompt_user "请输入RouterOS WAN接口名称" WAN_INTERFACE "internet" is_not_empty
    prompt_user "请输入IP检测和DNS更新间隔(秒)" DNS_UPDATE_INTERVAL "10" is_valid_port

    info_msg "\n--- Cloudflare API 配置 ---"
    prompt_user "请输入Cloudflare API Token" CLOUDFLARE_API_TOKEN "" is_not_empty
    prompt_user "请输入Cloudflare Zone ID (如果API Token权限未限制到特定Zone, 留空则脚本会尝试自动检测)" CLOUDFLARE_ZONE_ID ""

    info_msg "\n--- 内部服务器证书配置 ---"
    prompt_user "请选择Let's Encrypt证书环境 (staging/production)" CERT_ENVIRONMENT "staging" is_staging_or_production

    info_msg "\n--- 安装部署配置 ---"
    local default_install_dir="${HOME}/matrix" # 使用 eval 来解析 ~
    eval default_install_dir="$default_install_dir" # 确保 ~ 被正确展开
    prompt_user "请输入Matrix服务安装目录" INSTALL_DIR "$default_install_dir" is_not_empty
    prompt_user "请输入Helm Release名称" HELM_RELEASE_NAME "matrix-stack" is_not_empty
    prompt_user "请输入Helm Namespace" HELM_NAMESPACE "matrix" is_not_empty
}

main() {
    welcome_message
    check_dependencies

    if [ ! -f "$CONFIG_TEMPLATE" ]; then
        error_exit "配置文件模板 '$CONFIG_TEMPLATE' 未找到！脚本无法继续。"
    fi

    # 如果配置文件不存在，或用户选择重新配置，则从模板创建
    if [ -f "$CONFIG_FILE" ]; then
        read -r -p "找到现有配置文件 '$CONFIG_FILE'。是否加载现有值并在此基础上修改? (yes/no, no将从模板重新开始): " use_existing_config
        if [ "$use_existing_config" != "yes" ]; then
            info_msg "将从模板 '$CONFIG_TEMPLATE' 重新创建 '$CONFIG_FILE'。"
            cp "$CONFIG_TEMPLATE" "$CONFIG_FILE" || error_exit "无法从模板复制配置文件。"
        else
            info_msg "加载现有配置文件 '$CONFIG_FILE'。"
            # 确保模板中新增的占位符也能被正确处理，如果旧config缺少某些行，sed/awk的gsub不会出错
        fi
    else
        cp "$CONFIG_TEMPLATE" "$CONFIG_FILE" || error_exit "无法从模板创建配置文件。"
        info_msg "已从模板创建配置文件 '$CONFIG_FILE'。"
    fi

    chmod +w "$CONFIG_FILE" || error_exit "无法写入配置文件 '$CONFIG_FILE'。"

    collect_configurations

    success_msg "\n配置收集完成！"
    echo "请仔细检查 '$CONFIG_FILE' 文件中的所有配置项。"
    echo "-------------------------------------------------------"
    cat "$CONFIG_FILE"
    echo "-------------------------------------------------------"

    # 最终确认前，再处理一次DOMAIN相关的占位符，确保所有%%DOMAIN%%都被替换
    local final_domain_val=$(grep "^DOMAIN=" "$CONFIG_FILE" | head -n 1 | cut -d'=' -f2 | tr -d '"')
    if [[ "$final_domain_val" != "%%DOMAIN%%" ]] && [ -n "$final_domain_val" ]; then
        awk -v val="$final_domain_val" '{gsub(/%%DOMAIN%%/, val); print}' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
    fi


    read -r -p "确认以上配置正确并继续安装吗? (yes/no): " confirmation
    if [ "$confirmation" != "yes" ]; then
        error_exit "安装已取消。"
    fi

    info_msg "配置已确认。后续步骤将基于 '$CONFIG_FILE' 中的设置进行。"
    # 后续的安装步骤将在这里调用
    # 例如: source ./scripts/install_k3s.sh
    # source ./scripts/deploy_matrix.sh
}

# 执行主函数
main
