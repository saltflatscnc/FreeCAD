# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2026 Salt Flats CNC                                     *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import FreeCAD
import Path
import Path.Dressup.Gui.LeadInOut as PathDressupLeadInOut
import Path.Dressup.Tags as PathDressupTags
import Path.Main.Job as PathJob
import Path.Op.Profile as PathProfile

from CAMTests.PathTestUtils import PathTestBase


TAG_TOP = 3.0


class TestDressupLeadInOut(PathTestBase):
    """Unit tests for the LeadInOut dressup."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("TestDressupLeadInOut")
        box = self.doc.addObject("Part::Box", "Box")
        box.Length = 200
        box.Width = 100
        box.Height = 18
        self.doc.recompute()
        PathJob.Create("Job", [box], None)

    def tearDown(self):
        FreeCAD.closeDocument("TestDressupLeadInOut")

    def makeProfile(self, stepDown=20):
        profile = PathProfile.Create("Profile")
        profile.Side = "Outside"
        profile.Direction = "CW"
        for prop in ("StartDepth", "FinalDepth", "StepDown"):
            profile.setExpression(prop, None)
        profile.StartDepth = 18
        profile.FinalDepth = -0.25
        profile.StepDown = stepDown
        self.doc.recompute()
        return profile

    def makeTags(self, base, positions=None):
        tags = PathDressupTags.Create(base)
        tags.Width = 15
        tags.Height = TAG_TOP + 0.25
        tags.Angle = 90
        tags.Radius = 0
        self.doc.recompute()
        if positions:
            tags.Positions = positions
        else:
            tags.Proxy.generateTags(tags, 4)
        self.doc.recompute()
        return tags

    def makeLeadInOut(self, base, offsetOut=0):
        obj = self.doc.addObject("Path::FeaturePython", "LeadInOutDressup")
        dressup = PathDressupLeadInOut.ObjectDressup(obj)
        obj.Base = base
        dressup.setup(obj)
        obj.OffsetOut = offsetOut
        self.doc.recompute()
        return obj

    def rapids(self, obj):
        return [cmd for cmd in obj.Path.Commands if cmd.Name in Path.Geom.CmdMoveRapid]

    def overTags(self, obj):
        """Horizontal moves over the top of a tag, as (x, y) of their end points."""
        moves = []
        z = None
        for cmd in obj.Path.Commands:
            onTop = "Z" in cmd.Parameters and Path.Geom.isRoughly(cmd.z, TAG_TOP, 0.01)
            if cmd.Name in Path.Geom.CmdMoveStraight and onTop and z is not None:
                if Path.Geom.isRoughly(z, TAG_TOP, 0.01):
                    moves.append((round(cmd.x, 3), round(cmd.y, 3)))
            if "Z" in cmd.Parameters:
                z = cmd.z
        return moves

    def test00(self):
        """Verify tags do not split a profile into separate lead-in/out segments."""
        profile = self.makeProfile()
        plain = self.makeLeadInOut(profile)
        tagged = self.makeLeadInOut(self.makeTags(profile))

        self.assertEqual(len(self.rapids(tagged)), len(self.rapids(plain)))

    def test01(self):
        """Verify the tags survive the lead-in/out dressup."""
        profile = self.makeProfile()
        tags = self.makeTags(profile)
        tagged = self.makeLeadInOut(tags)

        self.assertTrue(self.overTags(tags))
        self.assertEqual(self.overTags(tagged), self.overTags(tags))

    def test02(self):
        """Verify overtravel past the start goes over a tag there instead of through it."""
        profile = self.makeProfile()
        # the profile starts at the top right corner and goes down the right side
        tags = self.makeTags(
            profile, [FreeCAD.Vector(202.5, 85, 0), FreeCAD.Vector(-2.5, 50, 0)]
        )
        tagged = self.makeLeadInOut(tags, offsetOut=40)

        overTags = self.overTags(tagged)
        self.assertEqual(len(overTags), 3)
        self.assertEqual(overTags[0], overTags[-1])

    def test03(self):
        """Verify step downs still get a lead-in/out each with tags on the last pass."""
        profile = self.makeProfile(stepDown=6)
        plain = self.makeLeadInOut(profile)
        tagged = self.makeLeadInOut(self.makeTags(profile))

        self.assertGreater(len(self.rapids(plain)), 4)
        self.assertEqual(len(self.rapids(tagged)), len(self.rapids(plain)))
