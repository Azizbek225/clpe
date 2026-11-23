// Windows release build'da qo'shimcha konsol oynasini yashirish
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    clpe_desktop_lib::run()
}
