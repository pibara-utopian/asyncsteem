#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
${DIR}/wtw_make_json.py
${DIR}/wtw_process_json.py
${DIR}/wtw_scp.py
${DIR}/wtw_post.py
