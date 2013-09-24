import uuid;
import time;
import re;
import traceback;
uuid._uuid_generate_time = None;
uuid._uuid_generate_random = None;

class PktMsgPart:
	
	def __init__(self,num,msg):
		self.num = num;
		self.msg = msg;

class PktMessage:
	
	def __init__(self,addr,port,ident):
		self.parts = [];
		self.addr = addr;
		self.port = port;
		self.ident = ident;
		self.ts = int(time.time());
		self.p = None;
		self.complete = False;
	
	# Sort as we insert.
	def add_part(self,num,tmsg,pmark,emark,mmark,multi_part=True):
		self.ts = int(time.time()); # renew timestamp.
		msg = tmsg;
		# if num == 0, then grab the properties.
		mloc = msg.find(mmark);
		smsg = msg;
		if(mloc != -1):
			smsg = msg[:mloc];
			msg = msg[mloc:];
		if pmark in smsg:
			pt = msg.split(pmark);
			ptl = len(pt);
			self.p = pt[:(ptl-1)];
			msg = pt[(ptl-1)];

		# check if complete.
		if emark in msg:
			self.complete = True;
			msg = msg.replace(emark,"");

		# clean the msg separators off.
		mm = msg.split(mmark);
		ss = "";
		ml = len(mm);
		mmm = "";
		for j in range(1,ml-1):
			mmm += ss + str(mm[j]);
			ss = mmark;
		msg = mmm;

		if(multi_part):
			p = PktMsgPart(num,msg);
			x = 0;
			z = len(self.parts);
			f = False;
			for x in range(0,z):
				y = self.parts[x];
				if(y.num >= num):
					f = True;
					break;
			if(not f):
				self.parts.append(p);
			else:
				self.parts.insert(x,p);

		return (msg,self.p);

	def is_complete(self,emark):
		ln = len(self.parts);
		lp = self.parts[ln-1];
		if(self.complete):
			j = -1;
			# all packets in sequence must be present. They're ordered, so increment through them.
			for x in self.parts:
				j += 1;
				if(x.num != j):
					return False;
			return True;
		return False;
	
	def is_expired(self,timeout):
		now = int(time.time());
		if((now - self.ts) > timeout):
			return True;
		return False;

	def destroy(self):
		del self.parts[:];

class PacketMessageManager:

	def __init__(self,max_size=2048):
		self.part_map = {};
		self.max_size = max_size;
		self.psep = "###";
		self.pksep = "[[%%%]]";
		self.msep = "<<<@$%!>>>!";
		self.emark = ">>>%%%<<<&";
		self.ka = "![{{X}}]!";
		self.ack = "![{{Y}}]!";
		self.hs = "![{{Z}}]!"; # handshake
		self.expire = 30; # in seconds
		self.hs_type = 3;
		self.ka_type = 2;
		self.ack_type = 1;
		self.msg_type = 0;
		self.ack_mode = False; # require acknowledgement.  Poor man's tcp.
	
	def add_data(self,d,addr,port):
		res = (None,False,0);
		try:
			# peel off the packet ident and number.
			ident = 0;
			num = 0;
			msg = "";
			ss = d.split(self.pksep);
			ident = ss[0];
			num = int(ss[1]);
			am = int(ss[2]);
			msg = ss[3];
			pk = None;
			if(am != 0):
				# Add the message part to the part_map
				if ident in self.part_map:
					pk = self.part_map[ident];
					pk.add_part(num,msg,self.psep,self.emark,self.msep);
				else:
					pk = PktMessage(addr,port,ident);
					pk.add_part(num,msg,self.psep,self.emark,self.msep);
					self.part_map[ident] = pk;		
				# Perform message integrity check.
				if(pk.is_complete(self.emark)):
					return self.pop_msg(ident,num,am);
				else:
					return (num,ident,am);
			else:
				# Not a split message (as it doesn't care about dropped packets).
				pk = PktMessage(addr,port,ident);
				smsg, sp = pk.add_part(num,msg,self.psep,self.emark,self.msep,False);
				return (num,ident,am,smsg,sp);
				#return self.pop_msg(ident,num,am); # no acknowledge?  No split.
		except Exception,e:
			print "\n---------\n";
			#print str(e)
			#traceback.print_exc(file=sys.stdout);
			traceback.print_exc()
			print "\n---------\n";
			pass;
		return res;
	
	def get_msg_type(self,d):
		if self.pksep in d:
			return self.msg_type;
		elif self.hs in d:
			return self.hs_type;

		sk = d.split(self.ka);
		sa = d.split(self.ack);
		skl = len(sk);
		sal = len(sa);
		if(skl > 1):
			if((sk[skl-1] == "") or (sk[skl-1] != None)):
				return self.ka_type;
		if(sal > 1):
			if((sa[sal-1] == "") or (sa[sal-1] != None)):
				return self.ack_type;
		return self.msg_type;
	
	def clear_data(self):
		#del self.parts[:];
		self.part_map.clear();

	def check_hs_packet(self,pkt):
		raw = int(pkt.replace(self.hs,""));
		if(raw == 0):
			return 1;
		return raw;

	def hs_packet(self,info=0):
		return str(info) + self.hs;

	def ka_packet(self):
		return self.ka;

	def ack_packet(self,num,ident):
		return str(num) + self.ack + str(ident) + self.ack;

	def parse_ack(self,pkt):
		s = pkt.split(self.ack);
		if(len(s) > 2):
			return (s[0],s[1]); # (num,ident)
		return None;

	# p is params, s is msg
	def create_msg_list(self,s,p=None,ack_mode=0):
		if((uuid._uuid_generate_time != None)or(uuid._uuid_generate_random != None)):
			uuid._uuid_generate_time = None;
			uuid._uuid_generate_random = None;

		uid = str(uuid.uuid4());
		res = [];
		prefix = "";
		psize = 0;
		if(p != None):
			for x in p:
				prefix += str(x) + str(self.psep);
		psize = len(prefix);
		msize = len(self.msep) * 2;
		esize = len(self.emark);
		osize = psize + msize;

		asize = self.max_size - osize;
		c,cs = len(s), asize;
		m = None;
		ident = "";
		j = -1;
		i = 0;
		tsize = 0;
		#for i in range(0,c,cs):
		while(i < c):
			j += 1;
			if(m != None):
				res.append(m);
			ident = uid + self.pksep + str(j) + self.pksep + str(ack_mode) + self.pksep;
			isize = len(ident);
			if(j > 1):
				prefix = "";
			psize = len(prefix);
			pre = ident + prefix;
			cs =  self.max_size - (msize + psize + isize);
			x = str(s[i:i+cs]);
			i += cs;
			m = pre + self.msep + x + self.msep
			tsize = msize + psize + isize + len(x);
		if(m != None):
			if((self.max_size - tsize) >= esize):
				res.append(m + self.emark);
			else:
				res.append(m);
				j += 1;
				ident = uid + self.pksep + str(j) + self.pksep + str(ack_mode) + self.pksep;
				res.append(ident + self.emark);
		return (res,ident);

	def pop_msg(self,num,ident,am):
		pk = self.part_map[ident];
		# peel the params off the first part.
		p = [];
		pt = [];
		m = "";
		mm = None;
		msg = "";
		pl = len(pk.parts);
		# Construct the msg.
		for i in range(0,pl):
			x = pk.parts[i];
			msg += str(x.msg);
		p = pk.p; # Grab the properites
		res = (num,ident,am,msg,p);
		# cleanup
		del self.part_map[ident];
		pk.destroy();
		# return results
		return res;
