// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only
// internal/pkg/secret/secret.go

package syn2mas

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

func scaleDownSynapse(client kubernetes.Interface, namespace string) map[string]int32 {
	ctx := context.Background()

	stsClient := client.AppsV1().StatefulSets(namespace)
	sts, err := stsClient.List(ctx, metav1.ListOptions{
		LabelSelector: "app.kubernetes.io/name=synapse",
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
		fmt.Printf("Setting replicas 0 on %s", s.Name)
		if _, err := stsClient.Update(ctx, &s, metav1.UpdateOptions{}); err != nil {
			fmt.Println(err)
		}
	}

	for {
		fmt.Println("Waiting for replicas to be 0 on synapse replicas" )
		sts, err := stsClient.List(ctx, metav1.ListOptions{
			LabelSelector: "app.kubernetes.io/name=synapse",
		})
		if err != nil {
			fmt.Println(err)
			os.Exit(1)
		}
		allStsDown := true
		for _, s := range sts.Items {
			if s.Status.AvailableReplicas != 0 {
				time.Sleep(time.Second)
				allStsDown = false
			}
		}
		if (allStsDown) {
			break
		}
	}
	return stsReplicas
}

func scaleBack(client kubernetes.Interface, namespace string, scaledSts map[string]int32) {
	ctx := context.Background()

	stsClient := client.AppsV1().StatefulSets(namespace)
	for stsName, replicas := range scaledSts{
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

func RunSyn2MAS(client kubernetes.Interface, namespace string, synapseConfigPath string, masConfigMap string) {
	originStsReplicas := scaleDownSynapse(client, namespace)
	// Run syn2mas cli, and in case of failure, scale back synapse up
	cmd := exec.Command("mas-cli", "syn2mas", "migrate", "--config", masConfigMap, "--synapse-config", synapseConfigPath)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err := cmd.Run()
	if err != nil {
			// Detailed error handling
			if exitError, ok := err.(*exec.ExitError); ok {
					fmt.Printf("Command failed with status: %v\n", exitError.ExitCode())
					scaleBack(client, namespace, originStsReplicas)
			}
	}
}
