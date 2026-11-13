use board_misoc::csr;

const EEM_POWER_MAX_RETRY: u8 = 5;
static mut EEM_POWER_RETRY: u8 = 0;

pub fn tick() {
    unsafe {
        if EEM_POWER_RETRY > EEM_POWER_MAX_RETRY || csr::eem_power_control::power_fault_read() != 1
        {
            return;
        }
        if EEM_POWER_RETRY == EEM_POWER_MAX_RETRY {
            error!("Maximum attempts reached! EEM power is cut.");
        } else {
            error!(
                "EEM power fault detected! Retrying(attempt {})...",
                EEM_POWER_RETRY + 1
            );
            csr::eem_power_control::power_fault_write(1);
        }
        EEM_POWER_RETRY += 1;
    }
}
