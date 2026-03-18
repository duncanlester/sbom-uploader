API_URL="http://localhost:8081"

# Get JWT token (default admin credentials)
TOKEN=$(curl -s -X POST "$API_URL/api/v1/user/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=password" )

echo "Token: $TOKEN"

# Delete all projects
curl -s "$API_URL/api/v1/project?pageSize=1000" \
  -H "Authorization: Bearer $TOKEN" | \
jq -r '.[].uuid' | \
while read uuid; do
  echo "Deleting $uuid..."
  curl -s -X DELETE "$API_URL/api/v1/project/$uuid" \
    -H "Authorization: Bearer $TOKEN"
done
