/* xoreos - A reimplementation of BioWare's Aurora engine
 *
 * xoreos is the legal property of its developers, whose names
 * can be found in the AUTHORS file distributed with this source
 * distribution.
 *
 * xoreos is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 3
 * of the License, or (at your option) any later version.
 *
 * xoreos is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with xoreos. If not, see <http://www.gnu.org/licenses/>.
 */

/** @file
 *  The context handling the gameplay in KotOR games.
 */

#include <cassert>

#include "src/sound/sound.h"

#include "src/engines/aurora/util.h"

#include "src/engines/kotorbase/game.h"
#include "src/engines/kotorbase/area.h"

namespace Engines {

namespace KotORBase {

Game::Game(Engines::Console &console) : _console(&console) {
}

void Game::playMusic(const Common::UString &music) {
	if (_module && _module->isRunning()) {
		KotORBase::Area *area = _module->getCurrentArea();
		if (area)
			area->playAmbientMusic(music);

		return;
	}

	playMenuMusic(music);
}

void Game::stopMusic() {
	stopMenuMusic();

	if (_module && _module->isRunning()) {
		KotORBase::Area *area = _module->getCurrentArea();
		if (area)
			area->stopAmbientMusic();
	}
}

void Game::playMenuMusic(Common::UString music) {
	stopMenuMusic();

	if (music.empty())
		music = getDefaultMenuMusic();

	_menuMusic = playSound(music, Sound::kSoundTypeMusic, true);
}

void Game::stopMenuMusic() {
	SoundMan.stopChannel(_menuMusic);
}

Module &Game::getModule() {
	assert(_module);
	return *_module;
}

} // End of namespace KotORBase

} // End of namespace Engines
