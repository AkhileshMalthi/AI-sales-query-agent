#!/bin/bash
# This script runs a series of queries against the running API to check for correctness.

# Wait for the API to be available
until $(curl --output /dev/null --silent --head --fail http://localhost:8000/docs); do
    printf '.'
    sleep 5
done

echo "API is up!"

queries=(
  "Top 3 customers by order count"
  "Average order value by region"
  "Monthly revenue for 2024"
  "Products that have never been ordered"
  "Total spend by customer segment"
)

SUCCESS_COUNT=0

for q in "${queries[@]}"; do
  echo "Testing query: $q"
  # Make the API call and check if the 'results' array is not empty
  response=$(curl -s -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"$q\"}")
  
  result_length=$(echo "$response" | jq '.results | length')

  if [ "$result_length" -gt 0 ]; then
    echo "✓ SUCCESS"
    SUCCESS_COUNT=$((SUCCESS_COUNT+1))
  else
    echo "✗ FAILED - No results returned"
  fi
done

echo "$SUCCESS_COUNT / ${#queries[@]} queries succeeded."

if [ "$SUCCESS_COUNT" -ne "${#queries[@]}" ]; then
    exit 1
fi
