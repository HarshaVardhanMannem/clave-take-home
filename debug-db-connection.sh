#!/bin/bash
# Database Connection Debugging Script for Ubuntu/EC2
# Run this script to diagnose database connection issues

set -e

echo "========================================="
echo "Database Connection Debugging Script"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

# 1. Check if DATABASE_URL is set
echo "1. Checking environment variables..."
if [ -z "$DATABASE_URL" ]; then
    echo -e "${YELLOW}Warning: DATABASE_URL is not set${NC}"
    if [ -f .env ]; then
        echo "Loading from .env file..."
        export $(grep -v '^#' .env | xargs)
    fi
fi

if [ -n "$DATABASE_URL" ]; then
    # Extract hostname from DATABASE_URL
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    print_status 0 "DATABASE_URL is set"
    echo "  Host: $DB_HOST"
    echo "  Port: $DB_PORT"
else
    print_status 1 "DATABASE_URL is not set"
    exit 1
fi

echo ""

# 2. Test DNS resolution
echo "2. Testing DNS resolution..."
if nslookup $DB_HOST > /dev/null 2>&1; then
    DB_IP=$(nslookup $DB_HOST | grep -A 1 "Name:" | tail -1 | awk '{print $2}')
    print_status 0 "DNS resolution successful"
    echo "  Resolved IP: $DB_IP"
else
    print_status 1 "DNS resolution failed"
    echo "  Trying with dig..."
    if command -v dig &> /dev/null; then
        dig $DB_HOST +short
    fi
fi

echo ""

# 3. Test network connectivity
echo "3. Testing network connectivity..."
if [ -n "$DB_IP" ]; then
    if ping -c 2 $DB_IP > /dev/null 2>&1; then
        print_status 0 "Ping to $DB_IP successful"
    else
        print_status 1 "Ping to $DB_IP failed"
    fi
fi

# Test port connectivity
echo "4. Testing port connectivity..."
if command -v nc &> /dev/null; then
    if nc -zv -w 5 $DB_HOST $DB_PORT 2>&1 | grep -q "succeeded"; then
        print_status 0 "Port $DB_PORT is reachable"
    else
        print_status 1 "Port $DB_PORT is NOT reachable"
        echo "  This might be a firewall/security group issue"
    fi
elif command -v telnet &> /dev/null; then
    timeout 5 telnet $DB_HOST $DB_PORT 2>&1 | grep -q "Connected" && \
        print_status 0 "Port $DB_PORT is reachable" || \
        print_status 1 "Port $DB_PORT is NOT reachable"
else
    echo -e "${YELLOW}Warning: nc or telnet not available, skipping port test${NC}"
fi

echo ""

# 5. Check Docker network configuration
echo "5. Checking Docker network configuration..."
if docker ps > /dev/null 2>&1; then
    print_status 0 "Docker is running"
    
    # Check if container is running
    if docker ps | grep -q "restaurant-analytics-backend"; then
        print_status 0 "Backend container is running"
        
        # Test DNS from inside container
        echo "  Testing DNS from inside container..."
        if docker exec restaurant-analytics-backend nslookup $DB_HOST > /dev/null 2>&1; then
            print_status 0 "Container can resolve DNS"
        else
            print_status 1 "Container CANNOT resolve DNS"
            echo "  Checking container DNS settings..."
            docker exec restaurant-analytics-backend cat /etc/resolv.conf
        fi
        
        # Test connectivity from inside container
        echo "  Testing connectivity from inside container..."
        if docker exec restaurant-analytics-backend python -c "import socket; socket.create_connection(('$DB_HOST', $DB_PORT), timeout=5)" 2>/dev/null; then
            print_status 0 "Container can reach database"
        else
            print_status 1 "Container CANNOT reach database"
        fi
    else
        print_status 1 "Backend container is not running"
    fi
else
    print_status 1 "Docker is not running or not accessible"
fi

echo ""

# 6. Check firewall/security groups
echo "6. Checking firewall rules..."
if command -v ufw &> /dev/null; then
    UFW_STATUS=$(ufw status | head -1)
    echo "  UFW Status: $UFW_STATUS"
    if echo "$UFW_STATUS" | grep -q "inactive"; then
        echo -e "  ${YELLOW}UFW is inactive (this is usually fine for EC2)${NC}"
    else
        echo -e "  ${YELLOW}UFW is active - check if port $DB_PORT is allowed${NC}"
    fi
fi

echo ""
echo "7. EC2 Security Group Check (Manual):"
echo "  - Go to AWS Console → EC2 → Security Groups"
echo "  - Find your instance's security group"
echo "  - Ensure outbound rules allow:"
echo "    - Type: All traffic or Custom TCP"
echo "    - Port: $DB_PORT (or 5432 for PostgreSQL)"
echo "    - Destination: 0.0.0.0/0 (or Supabase IP range)"
echo ""

# 8. Test from host
echo "8. Testing connection from host..."
if command -v psql &> /dev/null; then
    echo "  Attempting PostgreSQL connection test..."
    # Extract connection details safely
    if echo "$DATABASE_URL" | grep -q "postgresql://"; then
        echo "  (Skipping actual connection test - use your credentials)"
    fi
else
    echo "  psql not installed, skipping connection test"
fi

echo ""
echo "========================================="
echo "Debugging Summary"
echo "========================================="
echo ""
echo "Common issues and solutions:"
echo ""
echo "1. DNS Resolution Failed:"
echo "   - Check /etc/resolv.conf in container"
echo "   - Try adding DNS servers to docker-compose.yml:"
echo "     dns:"
echo "       - 8.8.8.8"
echo "       - 8.8.4.4"
echo ""
echo "2. Port Not Reachable:"
echo "   - Check EC2 Security Group outbound rules"
echo "   - Check if Supabase allows connections from your IP"
echo "   - Verify firewall rules (ufw/iptables)"
echo ""
echo "3. Container Network Issues:"
echo "   - Try: docker network inspect <network_name>"
echo "   - Check docker-compose.yml network configuration"
echo "   - Restart Docker: sudo systemctl restart docker"
echo ""
echo "4. SSL/TLS Issues:"
echo "   - Supabase requires SSL connections"
echo "   - Verify DATABASE_URL includes sslmode=require"
echo ""

