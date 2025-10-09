// Copyright 2025 New Vector Ltd
//
// SPDX-License-Identifier: AGPL-3.0-only

package deploymentmarkers

import (
	"flag"
	"fmt"
	"strings"
)

const (
	FlagSetName = "deployment-markers"
)

type DeploymentMarkersOptions struct {
	Labels            map[string]string
	DeploymentMarkers []DeploymentMarker
}

type DeploymentMarker struct {
	Name          string
	Key           string
	Step          string
	NewValue      string
	AllowedValues []string
}

func ParseArgs(args []string) (*DeploymentMarkersOptions, error) {
	options := &DeploymentMarkersOptions{}

	deploymentMarkersSet := flag.NewFlagSet(FlagSetName, flag.ExitOnError)
	deploymentMarkers := deploymentMarkersSet.String("markers", "", "Comma-separated list of deployment markers, with Semi-colon separated list of previous allowed values in the format of `name:step:newValue:[allowedValues;..]`")
	labels := deploymentMarkersSet.String("labels", "", "Comma-separated list of labels for generated secrets, in the format of `key=value`")
	step := deploymentMarkersSet.String("step", "", "One of `pre` or `post`")

	err := deploymentMarkersSet.Parse(args)
	if err != nil {
		return nil, err
	}
	for _, deploymentMarkerArg := range strings.Split(*deploymentMarkers, ",") {
		parsedValue := strings.Split(deploymentMarkerArg, ":")
		if len(parsedValue) < 3 {
			return nil, fmt.Errorf("invalid deployment marker format, expect <name:key:newValue:[allowedValues;..]>: %s", deploymentMarkerArg)
		}
		parsedAllowedValues := strings.Split(parsedValue[3], ";")
		deploymentMarker := DeploymentMarker{Name: parsedValue[0], Key: parsedValue[1], Step: *step, NewValue: parsedValue[2], AllowedValues: parsedAllowedValues}
		options.DeploymentMarkers = append(options.DeploymentMarkers, deploymentMarker)
	}
	options.Labels = make(map[string]string)
	if *labels != "" {
		for _, label := range strings.Split(*labels, ",") {
			parsedLabelValue := strings.Split(label, "=")
			options.Labels[parsedLabelValue[0]] = parsedLabelValue[1]
		}
	}
	options.Labels["app.kubernetes.io/managed-by"] = "matrix-tools-deployment-markers"
	return options, nil
}
