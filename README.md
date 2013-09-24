Python_UDP_Tools
================

Some flexible UDP server/client and packet content management classes.


Example usage:

```python

# To use: 
#    SERVER_MODE: python <scriptname>
#    CLIENT_MODE: python <scriptname> client

from udp_tools import UDP_Server
import sys;

mode = 0;
if(len(sys.argv) > 1):
	mode = 1;

# HANDLE MESSAGE
def host_handle_msg(parent,msg,params,addr,port,pk_ident,ack_mode):
	print "Server: Message Received\n-------\n";
	print "Address: "+str(addr);
	print "Port: "+str(port);
	print "Params: "+str(params);
	print msg;

def client_handle_msg(parent,msg,props,addr,port,pk_ident,ack_mode):
	print "Client: Message Received\n-------\n";
	print "Address: "+str(addr);
	print "Port: "+str(port);
	print "Params: "+str(params);
	print msg;

# HANDLE CONNECTION EXPIRATION (keep-alive messages stop)
def host_handle_expire(parent,rem_addr,rem_port):
	print "Server: Client Disconnected\n=======\n";
	print "Address: "+str(rem_addr);
	print "Port: "+str(rem_port);

def client_handle_expire(parent,rem_addr,rem_port):
	print "Client: Server Disconnected\n=======\n";
	print "Address: "+str(rem_addr);
	print "Port: "+str(rem_port);

host_addr = "127.0.0.1";
host_port = 36500;

client_addr = "127.0.0.1";
client_port = 36501;

t_addr = client_addr;
t_port = client_port;

serv = UDP_Server();

if(mode == 0):
	print "Starting host...";
	# host
	serv.host_msg_handler = host_handle_msg;
	serv.host_exp_handler = host_handle_expire;
	serv.start_host(host_port);
else:
	# client
	print "Starting client...";
	serv.client_msg_handler = client_handle_msg;
	serv.client_exp_handler = client_handle_expire;
	ss = serv.start_client(host_addr,host_port,client_port);
	if(not ss):
		print "Failed to connect!";
		exit();
	t_port = host_port;
	t_addr = host_addr;

print "Ready.";

while(True):
	print "Your message: ",;
	s = sys.stdin.readline();
	serv.send(s,None,t_addr,t_port);

```

