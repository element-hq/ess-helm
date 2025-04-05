# SPDX-License-Identifier: AGPL-3.0-only

set shell := ["bash", "-euo", "pipefail", "-c"]
set export := false

chart_dir := "charts/matrix-stack"
ci_dir := chart_dir + "/ci"
scripts_dir := "scripts"
default_namespace := "ess"

lint-helm: install-deps
    @echo "Running chart-testing lint..."
    ./{{ scripts_dir }}/ct-lint.sh

lint-checkov values_file namespace=default_namespace: install-deps
    @echo "Running checkov with values file: {{ chart_dir }}/{{ values_file }} in namespace {{ namespace }}..."
    cd {{ chart_dir }} && HELM_NAMESPACE={{ namespace }} checkov -d . --framework helm --quiet --var-file {{ values_file }}

lint-kubeconform values_file: install-deps
    @echo "Running kubeconform validation with values file: {{ chart_dir }}/{{ values_file }}..."
    cd {{ chart_dir }} && helm template -f {{ values_file }} . | kubeconform -summary

lint-reuse: install-deps
    @echo "Running REUSE lint..."
    reuse lint

lint-shellcheck: install-deps
    @echo "Running shellcheck..."
    shellcheck {{ scripts_dir }}/*.sh

lint: lint-helm lint-reuse lint-shellcheck
    @echo "Running default checkov..."
    just lint-checkov ci/synapse-checkov-values.yaml
    @echo "Running default kubeconform..."
    just lint-kubeconform ci/nothing-enabled-values.yaml

install-deps:
    poetry install

build-helm-values: install-deps
    @echo "Assembling Helm chart values and schema..."
    ./{{ scripts_dir }}/assemble_helm_charts_from_fragments.sh
    @echo "Done. Commit changes to {{ chart_dir }}/values.yaml and {{ chart_dir }}/values.schema.json"

build-ci-values: install-deps
    @echo "Assembling CI values files..."
    ./{{ scripts_dir }}/assemble_ci_values_files_from_fragments.sh
    @echo "Done. Commit changes to files in {{ ci_dir }}"

set-version version:
    @echo "Setting chart version to {{ version }}..."
    ./{{ scripts_dir }}/set_chart_version.sh {{ version }}
    @echo "Done. Commit changes to {{ chart_dir }}/Chart.yaml"

build: build-helm-values build-ci-values

cluster-up *namespaces:
    @echo "Setting up test cluster..."
    {%- if namespaces -%}
    export ESS_NAMESPACES="{{ namespaces }}"
    {%- else -%}
    export ESS_NAMESPACES="{{ default_namespace }}"
    {%- endif -%}
    ./{{ scripts_dir }}/setup_test_cluster.sh
    @echo "Cluster setup complete. Use 'just cluster-kubeconfig' to get kubeconfig."

cluster-down:
    @echo "Destroying test cluster..."
    ./{{ scripts_dir }}/destroy_test_cluster.sh

cluster-kubeconfig:
    @echo "Run the following command to configure kubectl:"
    @echo "  kind export kubeconfig --name ess-helm"

cluster-deploy values_file namespace=default_namespace:
    @echo "Deploying chart with values {{ chart_dir }}/{{ values_file }} to namespace {{ namespace }}..."
    helm -n {{ namespace }} upgrade -i ess {{ chart_dir }} -f {{ chart_dir }}/ci/test-cluster-mixin.yaml -f {{ chart_dir }}/{{ values_file }}
    @echo "Deployment complete."

test keep_cluster='0' *pytest_args: install-deps
    @echo "Running integration tests..."
    export PYTEST_KEEP_CLUSTER={{ keep_cluster }}
    pytest test {{ pytest_args }}

template-inspect values_file template_path namespace=default_namespace *extra_args:
    @echo "Rendering template {{ template_path }} with values {{ chart_dir }}/{{ values_file }}..."
    cd {{ chart_dir }} && helm template -n {{ namespace }} -f {{ values_file }} . -s {{ template_path }} {{ extra_args }}

template-debug values_file template_path namespace=default_namespace *extra_args:
    @echo "Rendering template {{ template_path }} with values {{ chart_dir }}/{{ values_file }} (DEBUG)..."
    cd {{ chart_dir }} && helm template -n {{ namespace }} -f {{ values_file }} . -s {{ template_path }} --debug {{ extra_args }}

changelog-create fragment_name: install-deps
    @echo "Creating newsfragment: {{ fragment_name }}"
    cd {{ chart_dir }} && towncrier create {{ fragment_name }}

changelog-build: install-deps
    @echo "Building changelog..."
    cd {{ chart_dir }} && towncrier build --draft
    @echo "Changelog build preview complete."
