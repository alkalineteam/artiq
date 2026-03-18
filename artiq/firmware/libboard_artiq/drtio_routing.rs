use board_misoc::config;
#[cfg(has_drtio_routing)]
use board_misoc::csr;
use core::fmt;

#[cfg(has_drtio_routing)]
pub const DEST_COUNT: usize = 256;
#[cfg(not(has_drtio_routing))]
pub const DEST_COUNT: usize = 0;
pub const MAX_HOPS: usize = 32;
pub const INVALID_HOP: u8 = 0xff;

pub struct RoutingTable {
    table: [[u8; MAX_HOPS]; DEST_COUNT],
    master_destination: u8,
}

impl RoutingTable {
    // default routing table is for star topology with no repeaters
    fn default_master(default_n_links: usize) -> RoutingTable {
        let mut ret = RoutingTable {
            table: [[INVALID_HOP; MAX_HOPS]; DEST_COUNT],
            master_destination: 0,
        };
        let n_entries = default_n_links + 1;  // include local RTIO
        for i in 0..n_entries {
            ret.table[i][0] = i as u8;
        }
        for i in 1..n_entries {
            ret.table[i][1] = 0x00;
        }
        ret
    }

    pub fn from_config(default_n_links: usize) -> RoutingTable {
        let mut ret = RoutingTable::default_master(default_n_links);
        let ok = config::read("routing_table", |result| {
            if let Ok(data) = result {
                if data.len() == DEST_COUNT*MAX_HOPS {
                    for i in 0..DEST_COUNT {
                        for j in 0..MAX_HOPS {
                            ret.table[i][j] = data[i*MAX_HOPS+j];
                        }
                    }
                    return true;
                } else {
                    warn!("length of the configured routing table is incorrect");
                }
            }
            false
        });
        if !ok {
            info!("could not read routing table from configuration, using default");
        }
        ret.determine_master_destination();
        info!("routing table: {}", ret);
        ret
    }

    // use this by default on satellite, as they receive
    // the routing table from the master
    pub fn default_empty() -> RoutingTable {
        RoutingTable {
            table: [[INVALID_HOP; MAX_HOPS]; DEST_COUNT],
            master_destination: 0,
        }
    }

    // find the master's destination number
    // by finding the destination with 0 hop at 0 rank
    fn determine_master_destination(&mut self) {
        for i in 0..DEST_COUNT {
            if self.table[i][0] == 0 {
                self.master_destination = i as u8;
            }
        }
    }

    pub fn get_master_destination(&self) -> u8 {
        self.master_destination
    }

    // get the next hop
    pub fn get_hop(&self, destination: u8, rank: u8) -> u8 {
        self.table[destination as usize][rank as usize]
    }

    // get the link number
    // returns an Option which is Some(linkno) if it's a downstream destination
    // None if it's a local or upstream destination
    pub fn get_linkno(&self, _destination: u8, _rank: u8) -> Option<u8> {
        #[cfg(has_drtio_routing)]
        {
            let hop = self.table[_destination as usize][_rank as usize];
            #[cfg(has_drtiorep0)]
            let drtio_len = csr::DRTIOREP.len();
            #[cfg(not(has_drtiorep0))]
            let drtio_len = csr::DRTIO.len();
            if hop == 0 || hop > drtio_len as u8 {
                None
            } else {
                Some(hop - 1)
            }
        }
        #[cfg(not(has_drtio_routing))]
        {
            None
        }
    }

    pub fn set_hops(&mut self, destination: u8, hops: [u8; MAX_HOPS]) {
        self.table[destination as usize] = hops;
        // update the master destination if applicable
        if self.table[destination as usize][0] == 0 {
            self.master_destination = destination;
        }
    }

    pub fn get_hops(&self, destination: usize) -> [u8; MAX_HOPS] {
        self.table[destination]
    }
}

impl fmt::Display for RoutingTable {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "RoutingTable {{")?;
        for i in 0..DEST_COUNT {
            if self.table[i][0] != INVALID_HOP {
                write!(f, " {}:", i)?;
                for j in 0..MAX_HOPS {
                    if self.table[i][j] == INVALID_HOP {
                        break;
                    }
                    write!(f, " {}", self.table[i][j])?;
                }
                write!(f, ";")?;
            }
        }
        write!(f, " }}")?;
        Ok(())
    }
}

#[cfg(has_drtio_routing)]
pub fn interconnect_enable(routing_table: &RoutingTable, rank: u8, destination: u8) {
    let hop = routing_table.get_hop(destination, rank);
    unsafe {
        csr::routing_table::destination_write(destination);
        csr::routing_table::hop_write(hop);
    }
}

#[cfg(has_drtio_routing)]
pub fn interconnect_disable(destination: u8) {
    unsafe {
        csr::routing_table::destination_write(destination);
        csr::routing_table::hop_write(INVALID_HOP);
    }
}

#[cfg(has_drtio_routing)]
pub fn interconnect_enable_all(routing_table: &RoutingTable, rank: u8) {
    for i in 0..DEST_COUNT {
        interconnect_enable(routing_table, rank, i as u8);
    }
}

#[cfg(has_drtio_routing)]
pub fn interconnect_disable_all() {
    for i in 0..DEST_COUNT {
        interconnect_disable(i as u8);
    }
}
