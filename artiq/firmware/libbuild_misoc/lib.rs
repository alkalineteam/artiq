use std::env;
use std::fs::{self, File};
use std::io::{BufRead, BufReader};
use std::path::Path;

pub fn cfg() {
    let out_dir = env::var("BUILDINC_DIRECTORY").unwrap();

    let cfg_path = Path::new(&out_dir).join("generated").join("rust-cfg");
    println!("cargo:rerun-if-changed={}", cfg_path.to_str().unwrap());

    // TODO: Automatically generate these.
    println!("cargo::rustc-check-cfg=cfg(has_converter_spi)");
    println!("cargo::rustc-check-cfg=cfg(has_ddrphy)");
    println!("cargo::rustc-check-cfg=cfg(has_dfii)");
    println!("cargo::rustc-check-cfg=cfg(ddrphy_wlevel)");
    println!("cargo::rustc-check-cfg=cfg(has_drtio)");
    println!("cargo::rustc-check-cfg=cfg(has_drtio_eem)");
    println!("cargo::rustc-check-cfg=cfg(has_drtio_routing)");
    println!("cargo::rustc-check-cfg=cfg(has_error_led)");
    println!("cargo::rustc-check-cfg=cfg(has_ethmac)");
    println!("cargo::rustc-check-cfg=cfg(has_ethphy)");
    println!("cargo::rustc-check-cfg=cfg(has_grabber)");
    println!("cargo::rustc-check-cfg=cfg(has_i2c)");
    println!("cargo::rustc-check-cfg=cfg(has_kernel_cpu)");
    println!("cargo::rustc-check-cfg=cfg(has_rtio)");
    println!("cargo::rustc-check-cfg=cfg(has_rtio_analyzer)");
    println!("cargo::rustc-check-cfg=cfg(has_rtio_crg)");
    println!("cargo::rustc-check-cfg=cfg(has_rtio_dma)");
    println!("cargo::rustc-check-cfg=cfg(kernel_has_rtio_dma)");
    println!("cargo::rustc-check-cfg=cfg(has_rtio_log)");
    println!("cargo::rustc-check-cfg=cfg(has_rtio_moninj)");
    println!("cargo::rustc-check-cfg=cfg(has_si549)");
    println!("cargo::rustc-check-cfg=cfg(has_si5324)");
    println!("cargo::rustc-check-cfg=cfg(si5324_ext_ref)");
    println!("cargo::rustc-check-cfg=cfg(si5324_soft_reset)");
    println!("cargo::rustc-check-cfg=cfg(has_siphaser)");
    println!("cargo::rustc-check-cfg=cfg(has_slave_fpga_cfg)");
    println!("cargo::rustc-check-cfg=cfg(has_spiflash)");
    println!("cargo::rustc-check-cfg=cfg(has_uart)");
    println!("cargo::rustc-check-cfg=cfg(has_wrpll)");
    println!(r#"cargo::rustc-check-cfg=cfg(rtio_frequency, values("100.0", "125.0"))"#);
    println!("cargo::rustc-check-cfg=cfg(ext_ref_frequency)");
    println!(
        r#"cargo::rustc-check-cfg=cfg(ext_ref_frequency, values("10.0", "80.0", "100.0", "125.0"))"#
    );
    println!(r#"cargo::rustc-check-cfg=cfg(hw_rev, values("v1.0", "v1.1", "v2.0", "v2.1"))"#);
    println!(
        r#"cargo::rustc-check-cfg=cfg(soc_platform, values("efc", "kasli", "kc705", "phaser"))"#
    );
    println!(r#"cargo::rustc-check-cfg=cfg(target_arch, values("or1k"))"#);

    let f = BufReader::new(File::open(&cfg_path).unwrap());
    for line in f.lines() {
        println!("cargo:rustc-cfg={}", line.unwrap());
    }
}
