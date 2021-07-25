#!/bin/bash

template_src=$1
target=$2

mv ${template_src}/jekyll/* $target
mkdir -p ${target}/_data
