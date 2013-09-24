import socket;
import select;
import threading;
from threading import Thread;
import time;
import traceback;

from PacketMessageManager import PacketMessageManager;

# HANDLE MESSAGE
def _server_handle_msg(parent,msg,props,addr,port,pk_ident,ack_mode):
	pass;

def _client_handle_msg(parent,msg,props,addr,port,pk_ident,ack_mode):
	pass;

# HANDLE CONNECTION EXPIRATION (keep-alive messages stop)
def _server_handle_expire(parent,rem_addr,rem_port):
	pass;

def _client_handle_expire(parent,rem_addr,rem_port):
	pass;



class UDP_Endpoint:

	def __init__(self,addr,port):
		self.addr = addr;
		self.port = port;
		self.ts = int(time.time());
	
	def ts_update(self):
		self.ts = int(time.time());
	
	def check_expire(self,current_time=None,tlimit = 5):
		now = current_time;
		if(now == None):
			now = int(time.time());
		if((now - self.ts) > tlimit):
			return True;
		return False;

class UDP_Active_Send:

	def __init__(self,msg,num):
		self.msg = msg;
		self.num = num;
		self.tstamp = int(time.time());

class UDP_Send_Item:

	def __init__(self,msg,props,addr,port,ack_mode=0,send_type=0):
		self.addr = addr;
		self.port = port;
		self.msg = msg;
		self.props = props;
		self.ack_mode = ack_mode;
		self.send_type = send_type;

class UDP_Server:

	def __init__(self,addr="127.0.0.1",port=36500):
		# init
		self.addr = addr;
		self.port = port;

		# public
		self.safety = False;
		self.safety_timeout = 5; # 5 seconds
		self.check_interval = 1; # 1 second
		self.ka_timelimit = 10;  # 10 seconds
		self.conn_try_max = 10;  # 10 tries
		self.conn_try_int = 0.5; # half a second
		self.ack_try_int = 0.5;  # half a second
		self.max_clients = None; # none or 0 is no limit.
		
		# handlers
		self.server_msg_handler = _server_handle_msg;
		self.client_msg_handler = _client_handle_msg;
		self.server_exp_handler = _server_handle_expire;
		self.client_exp_handler = _client_handle_expire;

		# internal
		self.sock = None;
		self.tstamp = int(time.time());
		self.exit_cond = False;
		self.pk_mgr = PacketMessageManager();
		self.clients = {};
		self.server_mode = 0; # 0 is server, 1 is client
		self.rem_addr="127.0.0.1";
		self.rem_port=36500;
		self.sd_msg = [];
		self.act_send = [];
		self.act_ident = None;
		
		self.is_running = [False,False,False];
		self.ka_int = 1; # 1 second
		self.std_sleep = 0.05;
		self.debug_mode = True;

	def dlog(self,m):
		if(self.debug_mode):
			print m;

	def check_end(self,safety=True):
		self.safety = safety;
		while(not self.exit_cond):
			time.sleep(self.check_interval);
			self.tstamp = int(time.time());
		self.end_serve();

	def end_serve(self):
		self.exit_cond = True;

	def safety_check(self):
		now = int(time.time());
		if((now - self.tstamp) > self.safety_timeout):
			self.end_serve();
	
	def send(self,msg,props,addr,port,ack_mode=0,send_type=0):
		self.sd_msg.append(UDP_Send_Item(msg,props,addr,port,ack_mode,send_type));
	
	def shutdown(self,blocking=False):
		self.end_serve();
		if(blocking):
			while(not self.is_shutdown()):
				time.sleep(0.25);
			self.shutdown_cleanup();

	def shutdown_cleanup(self):
		try:
			self.sock.shutdown();
			self.sock.close();
			self.sock = None;
			self.clients.clear();
		except:
			pass;

	def is_shutdown(self):
		for x in self.is_running:
			if(x):
				return False;
		return True;

	def try_sdcu(self):
		if(self.is_shutdown()):
			self.shutdown_cleanup();

	# keep-alive method. (for use as a separate thread only)
	def ka_serve(self):
		self.is_running[2] = True;
		rem_list = [];
		while(not self.exit_cond):
			del rem_list[:];
			# send(self,msg,props,addr,port,ack_mode=0):   check_expire(self,current_time=None,tlimit = 5):
			ka_pkt = self.pk_mgr.hs_packet();
			now = int(time.time());
			if(self.server_mode == 0): # server_mode
				for k, v in self.clients.iteritems():
					ce = v.check_expire(now,self.ka_timelimit);
					if(ce):
						#del self.clients[k];
						rem_list.append(k);
						self.server_exp_handler(self,v.addr,v.port);
					else:
						self.send(ka_pkt,None,v.addr,v.port,0,self.pk_mgr.ka_type);
			else: 			   # client_mode
				for k, v in self.clients.iteritems():
					ce = v.check_expire(now,self.ka_timelimit);
					if(ce):
						#del self.clients[k];
						rem_list.append(k);
						self.client_exp_handler(self,v.addr,v.port);
					else:
						self.send(ka_pkt,None,v.addr,v.port,0,self.pk_mgr.ka_type);
			for k in rem_list:
				del self.clients[k];
			time.sleep(self.ka_int);

		self.is_running[2] = False;
		self.try_sdcu();
	
	# socket send message method. (for use as a separate thread only)
	def send_serve(self):
		self.is_running[1] = True;
		
		while(not self.exit_cond):
			if(self.sock == None):
				print "[SEND THREAD] No socket...";
				time.sleep(self.std_sleep);
				continue;
			if(len(self.sd_msg) <= 0):
				time.sleep(self.std_sleep);
				continue;
			mm = self.sd_msg[0];
			del self.sd_msg[0];
			st = mm.send_type;
			ma, ident = None, None;
			if(st == self.pk_mgr.msg_type):
				ma, ident = self.pk_mgr.create_msg_list(mm.msg,mm.props,mm.ack_mode);
			else:
				ma = [mm.msg];
			#print "Attempt send: [IP: "+str(mm.addr)+"  PORT: "+str(mm.port)+"] " + str(ma);
			del self.act_send[:];
			try:
				mal = len(ma);
				for i in range(0,mal):
					m = ma[i];
					#print "Attempt send: [IP: "+str(mm.addr)+"  PORT: "+str(mm.port)+"] " + str(m);
					self.sock.sendto(m, (mm.addr, int(mm.port)));
					if(mm.ack_mode == 1):
						self.act_send.append(UDP_Active_Send(m,i));
				# wait for all acks
				if(mm.ack_mode == 1):
					self.act_ident = ident;
					while(len(self.act_send) > 0):
						now = int(time.time());
						for m in self.act_send:
							if((now - m.tstamp) > self.ack_try_int):
								m.tstamp = int(time.time());
								self.sock.sendto(m.msg, (mm.addr, int(mm.port)));
						time.sleep(self.std_sleep);
			except Exception,e:
				print "\n---------\n";
				print str(m);
				#print str(e);
				#traceback.print_exc(file=sys.stdout);
				traceback.print_exc()
				print "\n---------\n";
				pass;
		print "Exiting send thread...";
		self.is_running[1] = False;
		self.try_sdcu();

	# socket recv message method. (for use as a separate thread only)
	def recv_serve(self):
		self.is_running[0] = True;
		if(self.sock == None):
			self.sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM);
			self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1);
			#self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1);
			self.sock.bind((self.addr,self.port));
			
			self.sock.setblocking(0);

		while(not self.exit_cond):
			try:
				data = None;
				addr = None;
				ready = select.select([self.sock], [], [], 2);
				if ready[0]:
					data, addr = self.sock.recvfrom(4096);
				if(self.safety):
					self.safety_check(); # only needs to run in one spawned thread. Guards against main thread dying prematurely and leaving spawned threads hanging.
				if(self.exit_cond):
					break;
				
				if((data != None)and(addr != None)):
					ip = ""+str(addr[0]);
					port = int(addr[1]);
					ep = ip+"_"+str(port);
					mt = self.pk_mgr.get_msg_type(data);
					
					if(mt == self.pk_mgr.hs_type):    # HANDSHAKE
						#self.dlog("(HANDSHAKE) [IP: "+str(ip)+"  PORT: "+str(port)+"]: "+data);
						if((self.max_clients == None)or(self.max_clients == 0)or(self.max_clients > len(self.clients))):
							self.send(self.pk_mgr.hs_packet(),None,ip,port,0,self.pk_mgr.hs_type); # Accept client.
							self.clients[ep] = UDP_Endpoint(ip,port);
						else:
							self.send(self.pk_mgr.hs_packet(2),None,ip,port); # Max clients already reached. Reject.
					elif(mt == self.pk_mgr.ka_type):  # KEEP-ALIVE
						#self.dlog("(KEEP-ALIVE) [IP: "+str(ip)+"  PORT: "+str(port)+"]: "+data);
						c = self.clients[ep];
						c.ts_update();
					elif(mt == self.pk_mgr.ack_type): # ACKNOWLEDGE
						#self.dlog("(ACKNOWLEDGE) [IP: "+str(ip)+"  PORT: "+str(port)+"]: "+data);
						# get ident and num
						num,ident = self.pk_mgr.parse_ack(data);
						if(ident == self.act_ident):
							asl = len(self.act_send);
							for i in range(0,asl):
								x = self.act_send[i];
								if(x.num == num):
									del self.act_send[i]; # confirmed receipt, remove.
									break;
					elif(mt == self.pk_mgr.msg_type): # MESSAGE RECIEVE
						#self.dlog("(MESSAGE RECIEVE) [IP: "+str(ip)+"  PORT: "+str(port)+"]: "+data);
						x = self.pk_mgr.add_data(data,ip,port);
						# (num,ident,am,smsg,sp);
						num,ident,am = x[0],x[1],x[2];
						# acknowledge?
						if(int(am) == 1):
							self.send(self.pk_mgr.ack_packet(num,ident),None,ip,port,0,self.pk_mgr.ack_type);
						# is it a completed message? if so, handle it.
						if(len(x) > 3):
							msg,props = x[3],x[4];
							if(self.server_mode == 0):
								self.server_msg_handler(self,msg,props,ip,port,ident,am);
							else:
								self.client_msg_handler(self,msg,props,ip,port,ident,am);
				else:
					time.sleep(self.std_sleep);
			except:
				pass;

		self.is_running[0] = False;
		self.try_sdcu();
	
	def launch_threads(self):
		self.exit_cond = False;
		Thread(target=self.recv_serve).start();
		Thread(target=self.send_serve).start();
		Thread(target=self.ka_serve).start();

	def start_server(self,port):
		self.addr = "127.0.0.1";
		self.port = int(port);
		self.server_mode = 0; # server
		self.shutdown(True); # blocking shutdown
		self.sock = None;
		
		self.launch_threads();

	# For clients.
	def start_client(self,remote_addr,remote_port,local_port=36500,local_addr="127.0.0.1"):
		self.addr = local_addr;
		self.port = int(local_port);
		self.rem_addr=remote_addr;
		self.rem_port=remote_port;
		self.server_mode = 1; # client
		self.shutdown(True); # blocking shutdown
		self.sock = None;
		# attempt connection
		self.sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM);
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1);
		#self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1);
		self.sock.bind((self.addr,self.port));
		self.sock.setblocking(0);
		
		m = self.pk_mgr.hs_packet();
		atts = 0;
		success = False;
		while(atts <= self.conn_try_max):
			atts += 1;
			try:
				self.sock.sendto(m, (self.rem_addr, int(self.rem_port)));
				ready = select.select([self.sock], [], [], self.conn_try_int);
				if ready[0]:
					data, addr = self.sock.recvfrom(4096);
					ck = self.pk_mgr.check_hs_packet(data);
					print "(CONNECT: "+str(ck)+") ["+str(data)+"]";
					if(ck == 1):
						success = True;
						self.clients.clear();
						ep = str(self.rem_addr)+"_"+str(self.rem_port);
						self.clients[ep] = UDP_Endpoint(self.rem_addr,self.rem_port);
						break;
					# If ck is something else, then server is too busy, or some other reason.
			except Exception,e:
				#print "\n---------\n";
				#print str(e)
				#print "\n---------\n";
				pass;
		if(not success):
			return False;

		self.launch_threads();
		return True;
