// Copyright 2025 New Vector Ltd
// Copyright 2025-2026 Element Creations Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only
// internal/pkg/secret/secret.go

package syn2mas

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

func scaleDownSynapse(client kubernetes.Interface, namespace string) map[string]int32 {
	ctx := context.Background()

	stsClient := client.AppsV1().StatefulSets(namespace)
	sts, err := stsClient.List(ctx, metav1.ListOptions{
		LabelSelector: "app.kubernetes.io/component=matrix-server",
	})
	stsReplicas := make(map[string]int32)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	for _, s := range sts.Items {
		stsReplicas[s.Name] = *s.Spec.Replicas
		noReplicas := int32(0)
		s.Spec.Replicas = &noReplicas
		fmt.Printf("Setting replicas 0 on %s\n", s.Name)
		if _, err := stsClient.Update(ctx, &s, metav1.UpdateOptions{}); err != nil {
			fmt.Println(err)
		}
	}

	for {
		fmt.Println("Waiting for replicas to be 0 on all synapse replicas")
		sts, err := stsClient.List(ctx, metav1.ListOptions{
			LabelSelector: "app.kubernetes.io/component=matrix-server",
		})
		if err != nil {
			fmt.Println(err)
			os.Exit(1)
		}
		allStsDown := true
		for _, s := range sts.Items {
			fmt.Printf("%s replicas are %d\n", s.Name, s.Status.AvailableReplicas)
			if s.Status.AvailableReplicas != 0 {
				time.Sleep(time.Second)
				allStsDown = false
			}
		}
		if allStsDown {
			break
		}
	}

	allPodsDown := false
	remainingRetries := 60
	maxRetriesEnv := os.Getenv("SYN2MAS_SCALE_DOWN_MAX_RETRIES")
	if len(maxRetriesEnv) != 0 {
		remainingRetries, err = strconv.Atoi(maxRetriesEnv)
		if err != nil {
			remainingRetries = 60
		}
	}
	for {
		fmt.Println("Waiting for all synapse pods to be gone...")
		podsClient := client.CoreV1().Pods(namespace)
		pods, err := podsClient.List(ctx, metav1.ListOptions{
			LabelSelector: "app.kubernetes.io/component=matrix-server",
		})
		if err != nil {
			fmt.Println(err)
			os.Exit(1)
		}
		podsFound := 0
		for _, pod := range pods.Items {
			if pod.Status.Phase != corev1.PodSucceeded {
				podsFound = podsFound + 1
			}
		}
		if podsFound != 0 {
			fmt.Printf("Pods remaining. Waiting %d seconds...\n", (remainingRetries))
			if remainingRetries <= 0 {
				break
			}
			time.Sleep(time.Second)
		} else {
			allPodsDown = true
			break
		}
		remainingRetries = remainingRetries - 1
	}

	if !allPodsDown {
		fmt.Println("StatefulSet are down, but pods matching matrix-server component are remaining. Something wrong is happening.")
		os.Exit(1)
	}
	return stsReplicas
}

func scaleBack(client kubernetes.Interface, namespace string, scaledSts map[string]int32) {
	ctx := context.Background()
	fmt.Println("Scaling back synapse")
	stsClient := client.AppsV1().StatefulSets(namespace)
	for stsName, replicas := range scaledSts {
		fmt.Printf("Scaling back to %d replicas on %s\n", replicas, stsName)
		sts, err := stsClient.Get(ctx, stsName, metav1.GetOptions{})
		if err != nil {
			fmt.Println(err)
			os.Exit(1)
		}
		sts.Spec.Replicas = &replicas
		_, err = stsClient.Update(ctx, sts, metav1.UpdateOptions{})
		if err != nil {
			fmt.Println(err)
		}
	}
}

func CallSyn2Mas(description string, arg ...string) int {
	fmt.Println("Running", description)
	cmd := exec.Command("/tmp-mas-cli/mas-cli", arg...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err := cmd.Run()
	fmt.Println(description, "ended")
	var exitError *exec.ExitError
	var ok bool
	if err != nil {
		// Detailed error handling
		if exitError, ok = err.(*exec.ExitError); ok {
			fmt.Printf("Command failed with status: %v\n", exitError.ExitCode())
			return exitError.ExitCode()
		} else {
			return 1
		}
	}
	return 0
}

func DryRunSyn2MAS(synapseConfigPath string, masConfigMap string) {
	// Run syn2mas check first
	ret := CallSyn2Mas("syn2mas check", "syn2mas", "check", "--config", masConfigMap, "--synapse-config", synapseConfigPath)
	if ret > 0 {
		os.Exit(ret)
	}

	// Then run migrate --dry-run
	ret = CallSyn2Mas("syn2mas migrate --dry-run", "syn2mas", "migrate", "--dry-run", "--config", masConfigMap, "--synapse-config", synapseConfigPath)
	if ret > 0 {
		os.Exit(ret)
	}
}

func RunSyn2MAS(client kubernetes.Interface, namespace string, synapseConfigPath string, masConfigMap string) {
	originStsReplicas := scaleDownSynapse(client, namespace)
	// Run syn2mas cli, and in case of failure, scale back synapse up
	ret := CallSyn2Mas("syn2mas", "syn2mas", "migrate", "--config", masConfigMap, "--synapse-config", synapseConfigPath)
	scaleBack(client, namespace, originStsReplicas)
	os.Exit(ret)
}
